package com.example.rag.common;

import lombok.Getter;

@Getter
public class BizException extends RuntimeException {

    private final String code;

    public BizException(String code, String message) {
        super(message);
        this.code = code;
    }

    public static BizException of(String code, String message) {
        return new BizException(code, message);
    }

    public static BizException notFound(String what) {
        return new BizException("NOT_FOUND", what + "不存在");
    }

    public static BizException forbidden(String message) {
        return new BizException("KB_FORBIDDEN", message);
    }
}
