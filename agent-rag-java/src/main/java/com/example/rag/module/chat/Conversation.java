package com.example.rag.module.chat;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("conversation")
public class Conversation {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    /** JSON 数组：本会话勾选的知识库 id。 */
    private String kbIds;

    private String title;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;
}
