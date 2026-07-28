package com.example.rag.infra.ai;

import com.example.rag.common.BizException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.net.http.HttpClient.Version;
import java.time.Duration;
import java.util.Map;
import java.util.function.Consumer;

/**
 * Python AI 服务客户端。SSE 流式读取 + Internal Token 鉴权。
 * 契约见 doc/03-服务接口设计.md。
 */
@Slf4j
@Component
public class AiClient {

    private final String baseUrl;
    private final String internalToken;
    private final HttpClient http;
    private final ObjectMapper om = new ObjectMapper();

    public AiClient(@Value("${rag.ai.base-url}") String baseUrl,
                    @Value("${rag.ai.internal-token}") String internalToken,
                    @Value("${rag.ai.connect-timeout-seconds}") int connectTimeoutSeconds) {
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.internalToken = internalToken;
        this.http = HttpClient.newBuilder()
                .version(Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(connectTimeoutSeconds))
                .build();
    }

    private HttpRequest.Builder postJson(String path, Object body) throws Exception {
        return HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + path))
                .header("Content-Type", "application/json")
                .header("X-Internal-Token", internalToken)
                .POST(HttpRequest.BodyPublishers.ofString(om.writeValueAsString(body)));
    }

    /** GET JSON 调用。 */
    public JsonNode get(String path) {
        try {
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + path))
                    .header("X-Internal-Token", internalToken)
                    .timeout(Duration.ofSeconds(60))
                    .GET().build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() >= 300) {
                throw BizException.of("AI_SERVICE_ERROR",
                        "AI 服务响应异常: " + resp.statusCode() + " " + resp.body());
            }
            return om.readTree(resp.body());
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw BizException.of("AI_SERVICE_ERROR", "调用 AI 服务失败: " + e.getMessage());
        }
    }

    /** 普通 JSON 调用。 */
    public JsonNode post(String path, Object body) {
        try {
            HttpResponse<String> resp = http.send(
                    postJson(path, body).timeout(Duration.ofSeconds(60)).build(),
                    HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() >= 300) {
                throw BizException.of("AI_SERVICE_ERROR",
                        "AI 服务响应异常: " + resp.statusCode() + " " + resp.body());
            }
            return om.readTree(resp.body());
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw BizException.of("AI_SERVICE_ERROR", "调用 AI 服务失败: " + e.getMessage());
        }
    }

    /**
     * SSE 流式调用：逐事件回调，调用方负责转发与收尾。
     *
     * @param onEvent 回调（event 名, data JSON）；error 事件也会回调，由调用方决定中断
     */
    public void postSse(String path, Object body, Consumer<SseEvent> onEvent) {
        String currentEvent = "message";
        StringBuilder dataBuf = new StringBuilder();
        try {
            HttpResponse<java.io.InputStream> resp = http.send(
                    postJson(path, body).timeout(Duration.ofMinutes(10)).build(),
                    HttpResponse.BodyHandlers.ofInputStream());
            if (resp.statusCode() >= 300) {
                String errBody = new String(resp.body().readAllBytes(), StandardCharsets.UTF_8);
                throw BizException.of("AI_SERVICE_ERROR",
                        "AI 服务响应异常: " + resp.statusCode() + " " + errBody);
            }
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(resp.body(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        if (dataBuf.length() > 0) {
                            onEvent.accept(new SseEvent(currentEvent, dataBuf.toString()));
                        }
                        currentEvent = "message";
                        dataBuf.setLength(0);
                        continue;
                    }
                    if (line.startsWith("event:")) {
                        currentEvent = line.substring(6).trim();
                    } else if (line.startsWith("data:")) {
                        if (dataBuf.length() > 0) {
                            dataBuf.append("\n");
                        }
                        dataBuf.append(line.substring(5).trim());
                    }
                }
                if (dataBuf.length() > 0) {
                    onEvent.accept(new SseEvent(currentEvent, dataBuf.toString()));
                }
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw BizException.of("AI_SERVICE_ERROR", "AI 流式调用中断: " + e.getMessage());
        }
    }

    public JsonNode health() {
        try {
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + "/healthz"))
                    .timeout(Duration.ofSeconds(30))
                    .GET().build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            return om.readTree(resp.body());
        } catch (Exception e) {
            return om.createObjectNode().put("status", "error: " + e.getMessage());
        }
    }

    public record SseEvent(String event, String data) {
        public JsonNode json() {
            try {
                return new ObjectMapper().readTree(data);
            } catch (Exception e) {
                return null;
            }
        }
    }

    /** 便捷方法：提交文档入库任务。 */
    public JsonNode submitIngest(Map<String, Object> ingestBody) {
        return post("/v1/ingest", ingestBody);
    }

    public JsonNode deleteDocument(String kbCode, String docCode) {
        return post("/v1/documents/delete", Map.of("kb_id", kbCode, "doc_id", docCode));
    }
}
