package com.example.rag.module.chat;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.rag.common.BizException;
import com.example.rag.infra.ai.AiClient;
import com.example.rag.module.chat.mapper.ChatMessageMapper;
import com.example.rag.module.chat.mapper.ConversationMapper;
import com.example.rag.module.kb.KbService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

/**
 * 问答编排：Java 只做鉴权、历史组装、SSE 透传与落库，不理解检索细节。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ChatService {

    private static final int HISTORY_ROUNDS = 5;
    private static final long EMITTER_TIMEOUT_MS = 10 * 60 * 1000L;

    private final ConversationMapper conversationMapper;
    private final ChatMessageMapper messageMapper;
    private final KbService kbService;
    private final AiClient aiClient;
    private final ObjectMapper om = new ObjectMapper();

    public List<Conversation> listConversations(Long userId) {
        return conversationMapper.selectList(new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getUserId, userId)
                .orderByDesc(Conversation::getUpdatedAt));
    }

    public Conversation createConversation(Long userId, List<Long> kbIds) {
        kbService.resolveKbCodes(kbIds);  // 校验存在性
        Conversation c = new Conversation();
        c.setUserId(userId);
        try {
            c.setKbIds(om.writeValueAsString(kbIds));
        } catch (Exception e) {
            c.setKbIds("[]");
        }
        c.setTitle("新会话");
        conversationMapper.insert(c);
        return c;
    }

    public List<ChatMessage> listMessages(Long conversationId, Long userId) {
        mustOwnConversation(conversationId, userId);
        return messageMapper.selectList(new LambdaQueryWrapper<ChatMessage>()
                .eq(ChatMessage::getConversationId, conversationId)
                .orderByAsc(ChatMessage::getId));
    }

    private Conversation mustOwnConversation(Long id, Long userId) {
        Conversation c = conversationMapper.selectById(id);
        if (c == null || !c.getUserId().equals(userId)) {
            throw BizException.notFound("会话");
        }
        return c;
    }

    /**
     * 问答主流程：SseEmitter 透传 Python 事件流，done/error 时落库。
     */
    public SseEmitter chat(Long conversationId, String question, Long userId) {
        Conversation conversation = mustOwnConversation(conversationId, userId);
        List<Long> kbIds = parseKbIds(conversation.getKbIds());
        List<String> kbCodes = kbService.resolveKbCodes(kbIds);
        if (kbCodes.isEmpty()) {
            throw BizException.of("INVALID_REQUEST", "本会话没有可用的知识库");
        }

        // 0. 生成全链路 trace_id
        String traceId = UUID.randomUUID().toString().replace("-", "").substring(0, 16);

        // 1. 落库用户消息 + 组装历史
        saveMessage(conversationId, "user", question, traceId, null, null, null, null);
        if ("新会话".equals(conversation.getTitle())) {
            conversation.setTitle(question.length() > 30 ? question.substring(0, 30) + "..." : question);
            conversationMapper.updateById(conversation);
        }
        List<Map<String, String>> history = recentHistory(conversationId);

        // 2. 构造 Python 请求
        String sessionId = "conv_" + conversationId + "_" + System.currentTimeMillis();
        Map<String, Object> body = Map.of(
                "session_id", sessionId,
                "trace_id", traceId,
                "kb_ids", kbCodes,
                "question", question,
                "history", history,
                "options", Map.of("stream", true, "rewrite_query", true)
        );

        SseEmitter emitter = new SseEmitter(EMITTER_TIMEOUT_MS);
        StringBuilder fullAnswer = new StringBuilder();
        StringBuilder citationsJson = new StringBuilder("[]");
        StringBuilder debugJson = new StringBuilder("{}");
        StringBuilder rewritten = new StringBuilder();
        long start = System.currentTimeMillis();

        CompletableFuture.runAsync(() -> {
            try {
                aiClient.postSse("/v1/chat/completions", body, event -> {
                    try {
                        switch (event.event()) {
                            case "meta" -> {
                                JsonNode meta = event.json();
                                if (meta != null) {
                                    citationsJson.setLength(0);
                                    citationsJson.append(meta.path("citations").toString());
                                    rewritten.append(meta.path("rewritten_query").asText(""));
                                }
                                send(emitter, event);
                            }
                            case "token" -> {
                                JsonNode node = event.json();
                                if (node != null) {
                                    fullAnswer.append(node.path("delta").asText(""));
                                }
                                send(emitter, event);
                            }
                            case "done" -> {
                                JsonNode done = event.json();
                                if (done != null && done.has("retrieval")) {
                                    debugJson.setLength(0);
                                    debugJson.append(done.path("retrieval").toString());
                                }
                                send(emitter, event);
                            }
                            case "error" -> send(emitter, event);
                            default -> send(emitter, event);
                        }
                    } catch (Exception e) {
                        log.warn("forward event failed: {}", e.getMessage());
                    }
                });
                persistAssistantMessage(conversationId, fullAnswer.toString(), traceId,
                        citationsJson.toString(), debugJson.toString(),
                        rewritten.toString(), (int) (System.currentTimeMillis() - start));
                emitter.complete();
            } catch (Exception e) {
                log.error("chat stream error", e);
                try {
                    emitter.send(SseEmitter.event().name("error")
                            .data("{\"code\":\"AI_SERVICE_ERROR\",\"message\":\"" + e.getMessage() + "\"}"));
                } catch (Exception ignored) {
                }
                emitter.completeWithError(e);
            }
        });
        return emitter;
    }

    private void send(SseEmitter emitter, AiClient.SseEvent event) throws IOException {
        emitter.send(SseEmitter.event().name(event.event()).data(event.data()));
    }

    private void persistAssistantMessage(Long conversationId, String content, String traceId,
                                         String citations, String debug, String rewrittenQuery, int latencyMs) {
        if (content == null || content.isBlank()) {
            return;
        }
        saveMessage(conversationId, "assistant", content, traceId, citations, debug, rewrittenQuery, latencyMs);
        Conversation touch = new Conversation();
        touch.setId(conversationId);
        conversationMapper.updateById(touch);  // 触发 updated_at 刷新
    }

    private void saveMessage(Long conversationId, String role, String content, String traceId,
                             String citations, String debug, String rewrittenQuery, Integer latencyMs) {
        ChatMessage msg = new ChatMessage();
        msg.setConversationId(conversationId);
        msg.setTraceId(traceId);
        msg.setRole(role);
        msg.setContent(content);
        msg.setCitations(citations);
        msg.setRetrievalDebug(debug);
        msg.setRewrittenQuery(rewrittenQuery);
        msg.setLatencyMs(latencyMs);
        messageMapper.insert(msg);
    }

    private List<Map<String, String>> recentHistory(Long conversationId) {
        List<ChatMessage> recent = messageMapper.selectList(new LambdaQueryWrapper<ChatMessage>()
                .eq(ChatMessage::getConversationId, conversationId)
                .orderByDesc(ChatMessage::getId)
                .last("limit " + (HISTORY_ROUNDS * 2)));
        List<Map<String, String>> history = new ArrayList<>();
        for (int i = recent.size() - 1; i >= 0; i--) {
            ChatMessage m = recent.get(i);
            history.add(Map.of("role", m.getRole(), "content", m.getContent()));
        }
        return history;
    }

    private List<Long> parseKbIds(String json) {
        try {
            List<Long> ids = new ArrayList<>();
            for (JsonNode node : om.readTree(json)) {
                ids.add(node.asLong());
            }
            return ids;
        } catch (Exception e) {
            return List.of();
        }
    }

    /** 返回所有改写过的消息（跨对话），用于改写记录页。 */
    public List<Map<String, Object>> listRewrites() {
        // 查询所有有 rewritten_query 的 assistant 消息
        List<ChatMessage> assistantMsgs = messageMapper.selectList(new LambdaQueryWrapper<ChatMessage>()
                .isNotNull(ChatMessage::getRewrittenQuery)
                .ne(ChatMessage::getRewrittenQuery, "")
                .eq(ChatMessage::getRole, "assistant")
                .orderByDesc(ChatMessage::getId)
                .last("limit 200"));
        List<Map<String, Object>> result = new ArrayList<>();
        for (ChatMessage assistMsg : assistantMsgs) {
            // 找到这条 assistant 消息前面的 user 消息（同一个 conversation，id 更小）
            ChatMessage userMsg = messageMapper.selectOne(new LambdaQueryWrapper<ChatMessage>()
                    .eq(ChatMessage::getConversationId, assistMsg.getConversationId())
                    .eq(ChatMessage::getRole, "user")
                    .lt(ChatMessage::getId, assistMsg.getId())
                    .orderByDesc(ChatMessage::getId)
                    .last("limit 1"));
            if (userMsg == null) continue;
            // 只有改写后的 query 与原问题不同时才显示
            if (assistMsg.getRewrittenQuery() == null
                    || assistMsg.getRewrittenQuery().equals(userMsg.getContent())) continue;

            Conversation conv = conversationMapper.selectById(assistMsg.getConversationId());
            if (conv == null) continue;
            result.add(Map.of(
                    "messageId", assistMsg.getId(),
                    "traceId", assistMsg.getTraceId() != null ? assistMsg.getTraceId() : "",
                    "conversationId", assistMsg.getConversationId(),
                    "conversationTitle", conv.getTitle() != null ? conv.getTitle() : "",
                    "originalQuery", userMsg.getContent(),
                    "rewrittenQuery", assistMsg.getRewrittenQuery(),
                    "createdAt", assistMsg.getCreatedAt() != null ? assistMsg.getCreatedAt().toString() : ""
            ));
        }
        return result;
    }

    public void feedback(Long messageId, Integer feedback, String note, Long userId) {
        ChatMessage msg = messageMapper.selectById(messageId);
        if (msg == null) {
            throw BizException.notFound("消息");
        }
        mustOwnConversation(msg.getConversationId(), userId);
        msg.setFeedback(feedback);
        msg.setFeedbackNote(note);
        messageMapper.updateById(msg);
    }
}
