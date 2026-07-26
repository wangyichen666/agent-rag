package com.example.rag.module.kb;

import com.example.rag.common.Result;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Python 服务回调入口（内网调用，SecurityConfig 已放行 /internal/**）。
 */
@Slf4j
@RestController
@RequestMapping("/internal/callback")
@RequiredArgsConstructor
public class CallbackController {

    private final DocumentService documentService;

    @PostMapping("/ingest")
    public Result<Void> ingestCallback(@RequestBody JsonNode body) {
        String docId = body.path("doc_id").asText();
        String status = body.path("status").asText();
        Integer chunkCount = body.hasNonNull("chunk_count") ? body.path("chunk_count").asInt() : null;
        String error = body.hasNonNull("error") ? body.path("error").asText() : null;
        log.info("ingest callback: doc={} status={} chunks={}", docId, status, chunkCount);
        documentService.onIngestCallback(docId, status, chunkCount, error);
        return Result.ok();
    }
}
