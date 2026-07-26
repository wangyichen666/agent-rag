package com.example.rag.module.kb;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.example.rag.common.BizException;
import com.example.rag.infra.ai.AiClient;
import com.example.rag.infra.storage.MinioService;
import com.example.rag.module.kb.mapper.KbDocumentMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class DocumentService extends ServiceImpl<KbDocumentMapper, KbDocument> {

    private final MinioService minioService;
    private final AiClient aiClient;
    private final KbService kbService;

    @Value("${server.port:8080}")
    private int serverPort;

    @Value("${rag.callback-base-url:}")
    private String callbackBaseUrl;

    private static final List<String> SUPPORTED = List.of("pdf", "docx", "doc", "md", "markdown", "txt");

    public List<KbDocument> listByKb(Long kbId) {
        return list(new LambdaQueryWrapper<KbDocument>()
                .eq(KbDocument::getKbId, kbId)
                .orderByDesc(KbDocument::getId));
    }

    /**
     * 上传：存 MinIO → 落记录(pending) → 异步提交解析任务(parsing)。
     * 相同 hash 的文件在同一知识库内复用已有记录。
     */
    public KbDocument upload(Long kbId, MultipartFile file, Long userId) throws Exception {
        Kb kb = kbService.mustGet(kbId);
        String original = file.getOriginalFilename() == null ? "unnamed" : file.getOriginalFilename();
        String ext = extOf(original);
        if (!SUPPORTED.contains(ext)) {
            throw BizException.of("INVALID_REQUEST", "暂不支持的文件类型: " + ext);
        }

        byte[] bytes = file.getBytes();
        String hash = sha256(bytes);

        KbDocument existed = getOne(new LambdaQueryWrapper<KbDocument>()
                .eq(KbDocument::getKbId, kbId)
                .eq(KbDocument::getFileHash, hash)
                .last("limit 1"));
        if (existed != null) {
            throw BizException.of("DOC_DUPLICATED", "相同内容的文档已存在: " + existed.getFileName());
        }

        KbDocument doc = new KbDocument();
        doc.setDocCode("d_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));
        doc.setKbId(kbId);
        doc.setFileName(original);
        doc.setFileType(ext);
        doc.setFileSize(file.getSize());
        doc.setFileHash(hash);
        doc.setParseStatus(KbDocument.STATUS_PENDING);
        doc.setVersion(1);
        doc.setCreatedBy(userId);

        String objectPath = kb.getKbCode() + "/" + doc.getDocCode() + "/v1/" + original;
        minioService.upload(objectPath, new java.io.ByteArrayInputStream(bytes), bytes.length,
                file.getContentType() == null ? "application/octet-stream" : file.getContentType());
        doc.setMinioPath(objectPath);
        save(doc);

        submitIngestAsync(doc.getId());
        return doc;
    }

    @Async
    public void submitIngestAsync(Long documentId) {
        KbDocument doc = getById(documentId);
        if (doc == null) {
            return;
        }
        Kb kb = kbService.mustGet(doc.getKbId());
        try {
            doc.setParseStatus(KbDocument.STATUS_PARSING);
            updateById(doc);

            String fileUrl = minioService.presignedGetUrl(doc.getMinioPath());
            Map<String, Object> body = Map.of(
                    "kb_id", kb.getKbCode(),
                    "doc_id", doc.getDocCode(),
                    "file", Map.of("url", fileUrl, "name", doc.getFileName(), "type", doc.getFileType()),
                    "parser", "fast",
                    "chunk_config", Map.of("strategy", "structure"),
                    "callback_url", callbackBase() + "/internal/callback/ingest"
            );
            aiClient.submitIngest(body);
        } catch (Exception e) {
            log.error("submit ingest failed for doc {}: {}", doc.getDocCode(), e.getMessage());
            doc.setParseStatus(KbDocument.STATUS_FAILED);
            doc.setErrorMsg("提交解析任务失败: " + e.getMessage());
            updateById(doc);
        }
    }

    /** Python 回调入口（见 CallbackController）。 */
    public void onIngestCallback(String docCode, String status, Integer chunkCount, String error) {
        KbDocument doc = getOne(new LambdaQueryWrapper<KbDocument>()
                .eq(KbDocument::getDocCode, docCode).last("limit 1"));
        if (doc == null) {
            log.warn("ingest callback for unknown doc: {}", docCode);
            return;
        }
        if ("success".equals(status)) {
            doc.setParseStatus(KbDocument.STATUS_SUCCESS);
            doc.setChunkCount(chunkCount == null ? 0 : chunkCount);
            doc.setErrorMsg(null);
        } else {
            doc.setParseStatus(KbDocument.STATUS_FAILED);
            doc.setErrorMsg(error);
        }
        updateById(doc);
    }

    /**
     * 删除：先删向量（避免残留可检索内容）→ 删记录 → MinIO 延迟清理。
     */
    public void deleteDocument(Long documentId) {
        KbDocument doc = getById(documentId);
        if (doc == null) {
            throw BizException.notFound("文档");
        }
        Kb kb = kbService.mustGet(doc.getKbId());
        try {
            aiClient.deleteDocument(kb.getKbCode(), doc.getDocCode());
        } catch (Exception e) {
            throw BizException.of("AI_SERVICE_ERROR", "向量数据删除失败，请稍后重试: " + e.getMessage());
        }
        removeById(documentId);
        minioService.removeQuietly(doc.getMinioPath());
    }

    private String callbackBase() {
        if (callbackBaseUrl != null && !callbackBaseUrl.isBlank()) {
            return callbackBaseUrl.replaceAll("/+$", "");
        }
        return "http://127.0.0.1:" + serverPort;
    }

    private static String extOf(String name) {
        int dot = name.lastIndexOf('.');
        return dot < 0 ? "" : name.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    private static String sha256(byte[] data) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data));
    }
}
