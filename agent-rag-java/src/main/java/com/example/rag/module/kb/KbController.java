package com.example.rag.module.kb;

import com.example.rag.common.Result;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/kb")
@RequiredArgsConstructor
public class KbController {

    private final KbService kbService;

    @GetMapping
    public Result<List<Kb>> list(@AuthenticationPrincipal Long userId) {
        return Result.ok(kbService.listVisible(userId));
    }

    @PostMapping
    public Result<Kb> create(@AuthenticationPrincipal Long userId,
                             @Validated @RequestBody CreateKbRequest req) {
        return Result.ok(kbService.createKb(req.getName(), req.getDescription(), userId));
    }

    @GetMapping("/{id}")
    public Result<Kb> detail(@PathVariable Long id) {
        return Result.ok(kbService.mustGet(id));
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        Kb kb = kbService.mustGet(id);
        kb.setStatus(0);
        kbService.updateById(kb);
        return Result.ok();
    }

    @Data
    public static class CreateKbRequest {
        @NotBlank(message = "知识库名称不能为空")
        private String name;
        private String description;
    }
}
