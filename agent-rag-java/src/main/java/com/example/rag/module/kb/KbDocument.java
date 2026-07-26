package com.example.rag.module.kb;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("kb_document")
public class KbDocument {

    public static final String STATUS_PENDING = "pending";
    public static final String STATUS_PARSING = "parsing";
    public static final String STATUS_SUCCESS = "success";
    public static final String STATUS_FAILED = "failed";

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 传给 Python 侧的 doc_id。 */
    private String docCode;

    private Long kbId;

    private String fileName;

    private String fileType;

    private Long fileSize;

    private String fileHash;

    private String minioPath;

    /** pending / parsing / success / failed */
    private String parseStatus;

    private Integer chunkCount;

    private String errorMsg;

    private Integer version;

    private Long createdBy;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;
}
