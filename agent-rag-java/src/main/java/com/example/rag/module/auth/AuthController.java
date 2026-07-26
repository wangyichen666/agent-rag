package com.example.rag.module.auth;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.rag.common.BizException;
import com.example.rag.common.Result;
import com.example.rag.module.auth.mapper.SysUserMapper;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final SysUserMapper userMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    @PostMapping("/login")
    public Result<Map<String, Object>> login(@Validated @RequestBody LoginRequest req) {
        SysUser user = userMapper.selectOne(
                new LambdaQueryWrapper<SysUser>().eq(SysUser::getUsername, req.getUsername()));
        if (user == null || user.getStatus() != 1
                || !passwordEncoder.matches(req.getPassword(), user.getPasswordHash())) {
            throw BizException.of("UNAUTHORIZED", "用户名或密码错误");
        }
        String token = jwtService.issue(user.getId(), user.getUsername());
        return Result.ok(Map.of(
                "token", token,
                "user", Map.of("id", user.getId(),
                               "username", user.getUsername(),
                               "nickname", user.getNickname() == null ? "" : user.getNickname())
        ));
    }

    @Data
    public static class LoginRequest {
        @NotBlank(message = "用户名不能为空")
        private String username;
        @NotBlank(message = "密码不能为空")
        private String password;
    }
}
