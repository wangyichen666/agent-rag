package com.example.rag.module.chat;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("message")
public class ChatMessage {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 全链路追踪 ID（UUID 前 16 位），贯穿 Query → Rewrite → Retrieve → Rerank → Generate */
    private String traceId;

    private Long conversationId;

    /** user / assistant */
    private String role;

    private String content;

    private String rewrittenQuery;

    /** JSON 数组：引用列表（Python meta 事件透传）。 */
    private String citations;

    /** JSON：检索中间结果（rerank 分数等，观测用）。 */
    private String retrievalDebug;

    private Integer promptTokens;

    private Integer completionTokens;

    private Integer latencyMs;

    private Integer feedback;

    private String feedbackNote;

    private LocalDateTime createdAt;
}
