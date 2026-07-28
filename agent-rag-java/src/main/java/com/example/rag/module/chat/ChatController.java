package com.example.rag.module.chat;

import com.example.rag.common.Result;
import com.example.rag.infra.ai.AiClient;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ChatController {

    private final ChatService chatService;
    private final AiClient aiClient;

    @GetMapping("/conversations")
    public Result<List<Conversation>> conversations(@AuthenticationPrincipal Long userId) {
        return Result.ok(chatService.listConversations(userId));
    }

    @PostMapping("/conversations")
    public Result<Conversation> createConversation(@AuthenticationPrincipal Long userId,
                                                   @Validated @RequestBody CreateConversationRequest req) {
        return Result.ok(chatService.createConversation(userId, req.getKbIds()));
    }

    @GetMapping("/conversations/{id}/messages")
    public Result<List<ChatMessage>> messages(@PathVariable Long id,
                                              @AuthenticationPrincipal Long userId) {
        return Result.ok(chatService.listMessages(id, userId));
    }

    /** 问答：SSE 透传（前端协议与 Python 一致：meta/token/done/error）。 */
    @PostMapping(value = "/chat/completions", produces = "text/event-stream")
    public SseEmitter chat(@AuthenticationPrincipal Long userId,
                           @Validated @RequestBody ChatRequestBody req) {
        return chatService.chat(req.getConversationId(), req.getQuestion(), userId);
    }

    @PostMapping("/messages/{id}/feedback")
    public Result<Void> feedback(@PathVariable Long id,
                                 @AuthenticationPrincipal Long userId,
                                 @RequestBody Map<String, Object> body) {
        Integer feedback = body.get("feedback") == null ? null : ((Number) body.get("feedback")).intValue();
        String note = (String) body.getOrDefault("note", null);
        chatService.feedback(id, feedback, note, userId);
        return Result.ok();
    }

    /** 系统状态页：聚合 Python 侧健康检查。 */
    @GetMapping("/system/ai-health")
    public JsonNode aiHealth() {
        return aiClient.health();
    }

    // ========== Debug / Trace API ==========

    /** RAG 全链路调试：query → retrieve → rerank 全流程。 */
    @PostMapping("/debug/trace")
    public Result<JsonNode> debugTrace(@RequestBody Map<String, Object> body) {
        return Result.ok(aiClient.post("/v1/debug/trace", body));
    }

    /** 查看文档在向量库中的存储格式。 */
    @GetMapping("/debug/chunks/{kbId}/{docId}")
    public Result<JsonNode> debugChunks(@PathVariable String kbId, @PathVariable String docId) {
        return Result.ok(aiClient.get("/v1/debug/chunks/" + kbId + "/" + docId));
    }

    @Data
    public static class CreateConversationRequest {
        @NotEmpty(message = "请至少选择一个知识库")
        private List<Long> kbIds;
    }

    @Data
    public static class ChatRequestBody {
        @NotNull(message = "conversationId 不能为空")
        private Long conversationId;
        @NotBlank(message = "问题不能为空")
        private String question;
    }
}
