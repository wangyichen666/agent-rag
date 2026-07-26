package com.example.rag.infra.storage;

import io.minio.BucketExistsArgs;
import io.minio.GetPresignedObjectUrlArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import io.minio.RemoveObjectArgs;
import io.minio.http.Method;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.InputStream;
import java.util.concurrent.TimeUnit;

/**
 * MinIO 对象存储封装。路径规则：{kbCode}/{docCode}/v{version}/{fileName}。
 */
@Slf4j
@Service
public class MinioService {

    private final MinioClient client;
    private final String bucket;
    private final int presignExpireMinutes;

    public MinioService(@Value("${rag.minio.endpoint}") String endpoint,
                        @Value("${rag.minio.access-key}") String accessKey,
                        @Value("${rag.minio.secret-key}") String secretKey,
                        @Value("${rag.minio.bucket}") String bucket,
                        @Value("${rag.minio.presign-expire-minutes}") int presignExpireMinutes) {
        this.client = MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();
        this.bucket = bucket;
        this.presignExpireMinutes = presignExpireMinutes;
    }

    @PostConstruct
    public void ensureBucket() {
        try {
            boolean exists = client.bucketExists(BucketExistsArgs.builder().bucket(bucket).build());
            if (!exists) {
                client.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
                log.info("created minio bucket: {}", bucket);
            }
        } catch (Exception e) {
            log.warn("ensure bucket failed (minio not ready?): {}", e.getMessage());
        }
    }

    public String upload(String objectPath, InputStream in, long size, String contentType) {
        try {
            client.putObject(PutObjectArgs.builder()
                    .bucket(bucket)
                    .object(objectPath)
                    .stream(in, size, -1)
                    .contentType(contentType)
                    .build());
            return objectPath;
        } catch (Exception e) {
            throw new IllegalStateException("文件上传到对象存储失败: " + e.getMessage(), e);
        }
    }

    /** 生成预签名下载 URL，供 Python 服务拉取文件。 */
    public String presignedGetUrl(String objectPath) {
        try {
            return client.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
                    .method(Method.GET)
                    .bucket(bucket)
                    .object(objectPath)
                    .expiry(presignExpireMinutes, TimeUnit.MINUTES)
                    .build());
        } catch (Exception e) {
            throw new IllegalStateException("生成文件访问地址失败: " + e.getMessage(), e);
        }
    }

    public void removeQuietly(String objectPath) {
        try {
            client.removeObject(RemoveObjectArgs.builder().bucket(bucket).object(objectPath).build());
        } catch (Exception e) {
            log.warn("remove object failed: {} - {}", objectPath, e.getMessage());
        }
    }

    public String getBucket() {
        return bucket;
    }
}
