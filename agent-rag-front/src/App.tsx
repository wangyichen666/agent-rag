import { MessageOutlined, DatabaseOutlined, LogoutOutlined } from '@ant-design/icons'
import { App as AntdApp, Layout, Menu, Button, Space } from 'antd'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { getToken } from './api/client'
import { useAuthStore } from './stores/auth'
import ChatPage from './pages/ChatPage'
import KbPage from './pages/KbPage'
import LoginPage from './pages/LoginPage'

const { Header, Content } = Layout

function RequireAuth({ children }: { children: JSX.Element }) {
  if (!getToken()) return <Navigate to="/login" replace />
  return children
}

function Shell({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const logout = useAuthStore((s) => s.logout)
  const selected = location.pathname.startsWith('/kb') ? 'kb' : 'chat'
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <div style={{ color: '#fff', fontWeight: 600, whiteSpace: 'nowrap' }}>
          Agent RAG 知识库
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selected]}
          style={{ flex: 1, minWidth: 0 }}
          items={[
            { key: 'chat', icon: <MessageOutlined />, label: <Link to="/">对话</Link> },
            { key: 'kb', icon: <DatabaseOutlined />, label: <Link to="/kb">知识库管理</Link> },
          ]}
        />
        <Space>
          <Button type="text" icon={<LogoutOutlined />} style={{ color: '#fff' }} onClick={logout}>
            退出
          </Button>
        </Space>
      </Header>
      <Content style={{ padding: 16, height: 'calc(100vh - 64px)', overflow: 'auto' }}>
        {children}
      </Content>
    </Layout>
  )
}

export default function App() {
  return (
    <AntdApp>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Shell>
                <ChatPage />
              </Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/kb"
          element={
            <RequireAuth>
              <Shell>
                <KbPage />
              </Shell>
            </RequireAuth>
          }
        />
      </Routes>
    </AntdApp>
  )
}
