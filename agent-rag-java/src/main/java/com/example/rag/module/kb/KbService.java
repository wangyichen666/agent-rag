package com.example.rag.module.kb;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.example.rag.common.BizException;
import com.example.rag.module.kb.mapper.KbMapper;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

@Service
public class KbService extends ServiceImpl<KbMapper, Kb> {

    public Kb createKb(String name, String description, Long ownerId) {
        Kb kb = new Kb();
        kb.setKbCode("kb_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));
        kb.setName(name);
        kb.setDescription(description);
        kb.setOwnerId(ownerId);
        kb.setStatus(1);
        save(kb);
        return kb;
    }

    /**
     * M1 简化权限：全部登录用户可见所有启用中的知识库。
     * 二期按 kb_permission 过滤（query wrapper 加 in 条件），契约不变。
     */
    public List<Kb> listVisible(Long userId) {
        return list(new LambdaQueryWrapper<Kb>()
                .eq(Kb::getStatus, 1)
                .orderByDesc(Kb::getUpdatedAt));
    }

    public Kb mustGet(Long id) {
        Kb kb = getById(id);
        if (kb == null || kb.getStatus() != 1) {
            throw BizException.notFound("知识库");
        }
        return kb;
    }

    public List<String> resolveKbCodes(List<Long> kbIds) {
        if (kbIds == null || kbIds.isEmpty()) {
            throw BizException.of("INVALID_REQUEST", "请至少选择一个知识库");
        }
        return listByIds(kbIds).stream()
                .filter(k -> k.getStatus() == 1)
                .map(Kb::getKbCode)
                .toList();
    }
}
