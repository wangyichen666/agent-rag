package com.example.rag.module.kb;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("kb")
public class Kb {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 传给 Python 侧的 kb_id。 */
    private String kbCode;

    private String name;

    private String description;

    private String embeddingModel;

    /** JSON 字符串：{strategy, chunk_size, chunk_overlap, parent_child}。 */
    private String chunkConfig;

    private Long ownerId;

    private Integer status;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;
}
