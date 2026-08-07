package com.example.rag.common;

/**
 * 免登录模式：所有业务接口统一使用管理员账号（DataInitializer 初始化，id=1）。
 * 如需恢复登录鉴权，改回 @AuthenticationPrincipal 并启用 JWT 过滤器即可。
 */
public final class AuthDefaults {

    public static final long DEFAULT_USER_ID = 1L;

    private AuthDefaults() {
    }
}
