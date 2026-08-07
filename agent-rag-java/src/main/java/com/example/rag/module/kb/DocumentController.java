package com.example.rag.module.kb;

import com.example.rag.common.Result;
import com.example.rag.common.AuthDefaults;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentService documentService;

    @GetMapping("/kb/{kbId}/documents")
    public Result<List<KbDocument>> list(@PathVariable Long kbId) {
        return Result.ok(documentService.listByKb(kbId));
    }

    @PostMapping("/kb/{kbId}/documents")
    public Result<KbDocument> upload(@PathVariable Long kbId,
                                     @RequestParam("file") MultipartFile file) throws Exception {
        return Result.ok(documentService.upload(kbId, file, AuthDefaults.DEFAULT_USER_ID));
    }

    @DeleteMapping("/documents/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        documentService.deleteDocument(id);
        return Result.ok();
    }

    @PostMapping("/documents/{id}/reingest")
    public Result<Void> reingest(@PathVariable Long id) {
        documentService.submitIngestAsync(id);
        return Result.ok();
    }

    @Data
    public static class IngestCallbackBody {
        private String doc_id;
        private String status;
        private Integer chunk_count;
        private Long elapsed_ms;
        private String error;
    }
}
