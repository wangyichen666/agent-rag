package com.example.rag.module.kb;

import com.example.rag.common.Result;
import com.example.rag.infra.ai.AiClient;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 知识图谱：代理 Python AI 层图谱接口（JWT 保护，同 /api/kb/** 权限）。
 */
@RestController
@RequestMapping("/api/kb")
@RequiredArgsConstructor
public class GraphController {

    private final KbService kbService;
    private final AiClient aiClient;

    @GetMapping("/{id}/graph")
    public Result<JsonNode> graph(@PathVariable Long id,
                                  @RequestParam(defaultValue = "300") int limit) {
        Kb kb = kbService.mustGet(id);
        return Result.ok(aiClient.get("/v1/graph/" + kb.getKbCode() + "?limit=" + limit));
    }

    @GetMapping("/{id}/graph/stats")
    public Result<JsonNode> stats(@PathVariable Long id) {
        Kb kb = kbService.mustGet(id);
        return Result.ok(aiClient.get("/v1/graph/" + kb.getKbCode() + "/stats"));
    }
}
