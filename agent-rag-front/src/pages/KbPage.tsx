import { DeleteOutlined, PlusOutlined, ReloadOutlined, UploadOutlined } from '@ant-design/icons'
import {
  App,
  Button,
  Card,
  Col,
  Form,
  Input,
  List,
  Modal,
  Popconfirm,
  Row,
  Space,
  Table,
  Tag,
  Upload,
} from 'antd'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Kb, KbDocument, ParseStatus } from '../types'

const STATUS_TAG: Record<ParseStatus, { color: string; text: string }> = {
  pending: { color: 'default', text: '待解析' },
  parsing: { color: 'processing', text: '解析中' },
  success: { color: 'success', text: '已完成' },
  failed: { color: 'error', text: '失败' },
}

export default function KbPage() {
  const { message } = App.useApp()
  const [kbs, setKbs] = useState<Kb[]>([])
  const [currentKb, setCurrentKb] = useState<Kb | null>(null)
  const [docs, setDocs] = useState<KbDocument[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [form] = Form.useForm()
  const pollRef = useRef<number>()

  const loadKbs = useCallback(async () => {
    const list = await api.get<Kb[]>('/api/kb')
    setKbs(list)
    if (list.length > 0 && !currentKb) setCurrentKb(list[0])
  }, [currentKb])

  const loadDocs = useCallback(async (kb: Kb | null) => {
    if (!kb) {
      setDocs([])
      return
    }
    setDocs(await api.get<KbDocument[]>(`/api/kb/${kb.id}/documents`))
  }, [])

  useEffect(() => {
    loadKbs()
  }, [])

  // 解析中文档轮询刷新
  useEffect(() => {
    loadDocs(currentKb)
    window.clearInterval(pollRef.current)
    pollRef.current = window.setInterval(() => {
      setDocs((prev) => {
        if (prev.some((d) => d.parseStatus === 'parsing' || d.parseStatus === 'pending')) {
          loadDocs(currentKb)
        }
        return prev
      })
    }, 3000)
    return () => window.clearInterval(pollRef.current)
  }, [currentKb, loadDocs])

  const createKb = async () => {
    const values = await form.validateFields()
    await api.post('/api/kb', values)
    setCreateOpen(false)
    form.resetFields()
    message.success('知识库已创建')
    loadKbs()
  }

  const uploadFile = async (file: File) => {
    if (!currentKb) return
    try {
      await api.upload(`/api/kb/${currentKb.id}/documents`, file)
      message.success(`${file.name} 上传成功，开始解析`)
      loadDocs(currentKb)
    } catch (e: any) {
      message.error(e.message)
    }
  }

  return (
    <Row gutter={16} style={{ height: '100%' }}>
      <Col span={7}>
        <Card
          title="知识库"
          size="small"
          extra={
            <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              新建
            </Button>
          }
        >
          <List
            dataSource={kbs}
            renderItem={(kb) => (
              <List.Item
                onClick={() => setCurrentKb(kb)}
                style={{
                  cursor: 'pointer',
                  padding: '10px 12px',
                  borderRadius: 8,
                  background: currentKb?.id === kb.id ? '#e6f4ff' : undefined,
                }}
              >
                <List.Item.Meta title={kb.name} description={kb.description || '暂无描述'} />
              </List.Item>
            )}
          />
        </Card>
      </Col>
      <Col span={17}>
        <Card
          size="small"
          title={currentKb ? `文档管理 · ${currentKb.name}` : '文档管理'}
          extra={
            <Space>
              <Button icon={<ReloadOutlined />} onClick={() => loadDocs(currentKb)} />
              <Upload showUploadList={false} beforeUpload={(f) => (uploadFile(f), false)} disabled={!currentKb}>
                <Button type="primary" icon={<UploadOutlined />} disabled={!currentKb}>
                  上传文档
                </Button>
              </Upload>
            </Space>
          }
        >
          <Table<KbDocument>
            rowKey="id"
            size="small"
            dataSource={docs}
            pagination={false}
            columns={[
              { title: '文件名', dataIndex: 'fileName', ellipsis: true },
              { title: '类型', dataIndex: 'fileType', width: 70 },
              {
                title: '大小',
                dataIndex: 'fileSize',
                width: 100,
                render: (s: number) => (s > 1048576 ? `${(s / 1048576).toFixed(1)} MB` : `${Math.ceil(s / 1024)} KB`),
              },
              {
                title: '状态',
                dataIndex: 'parseStatus',
                width: 110,
                render: (s: ParseStatus, row) => (
                  <Space size={4}>
                    <Tag color={STATUS_TAG[s].color}>{STATUS_TAG[s].text}</Tag>
                    {s === 'success' && <span style={{ color: '#888', fontSize: 12 }}>{row.chunkCount} 块</span>}
                  </Space>
                ),
              },
              {
                title: '操作',
                width: 140,
                render: (_, row) => (
                  <Space>
                    {row.parseStatus === 'failed' && (
                      <Button
                        size="small"
                        onClick={async () => {
                          await api.post(`/api/documents/${row.id}/reingest`)
                          loadDocs(currentKb)
                        }}
                      >
                        重试
                      </Button>
                    )}
                    <Popconfirm
                      title="删除文档"
                      description="将同时删除其向量数据，确认？"
                      onConfirm={async () => {
                        await api.delete(`/api/documents/${row.id}`)
                        message.success('已删除')
                        loadDocs(currentKb)
                      }}
                    >
                      <Button size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  </Space>
                ),
              },
            ]}
          />
          {docs.some((d) => d.parseStatus === 'failed') && (
            <div style={{ marginTop: 8, color: '#a33', fontSize: 12 }}>
              {docs.find((d) => d.parseStatus === 'failed')?.errorMsg}
            </div>
          )}
        </Card>
      </Col>

      <Modal title="新建知识库" open={createOpen} onOk={createKb} onCancel={() => setCreateOpen(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input maxLength={50} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} maxLength={200} />
          </Form.Item>
        </Form>
      </Modal>
    </Row>
  )
}
