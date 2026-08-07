import { MessageOutlined, DatabaseOutlined, EyeOutlined, FolderOpenOutlined, HistoryOutlined, EditOutlined, ApartmentOutlined } from '@ant-design/icons'
import { App as AntdApp, Layout, Menu } from 'antd'
import { Link, Route, Routes, useLocation } from 'react-router-dom'
import ChatPage from './pages/ChatPage'
import KbPage from './pages/KbPage'
import TracePage from './pages/TracePage'
import StoragePage from './pages/StoragePage'
import RewritePage from './pages/RewritePage'
import HistoryPage from './pages/HistoryPage'
import GraphPage from './pages/GraphPage'

const { Header, Content } = Layout

function Shell({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const selected = location.pathname.startsWith('/kb') ? 'kb'
    : location.pathname.startsWith('/trace') ? 'trace'
    : location.pathname.startsWith('/storage') ? 'storage'
    : location.pathname.startsWith('/rewrites') ? 'rewrites'
    : location.pathname.startsWith('/conversations') ? 'conversations'
    : location.pathname.startsWith('/graph') ? 'graph'
    : 'chat'
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
            { key: 'trace', icon: <EyeOutlined />, label: <Link to="/trace">追溯</Link> },
            { key: 'storage', icon: <FolderOpenOutlined />, label: <Link to="/storage">向量库</Link> },
            { key: 'graph', icon: <ApartmentOutlined />, label: <Link to="/graph">知识图谱</Link> },
            { key: 'rewrites', icon: <EditOutlined />, label: <Link to="/rewrites">改写记录</Link> },
            { key: 'conversations', icon: <HistoryOutlined />, label: <Link to="/conversations">对话记录</Link> },
          ]}
        />
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
        <Route path="/" element={<Shell><ChatPage /></Shell>} />
        <Route path="/kb" element={<Shell><KbPage /></Shell>} />
        <Route path="/trace" element={<Shell><TracePage /></Shell>} />
        <Route path="/storage" element={<Shell><StoragePage /></Shell>} />
        <Route path="/graph" element={<Shell><GraphPage /></Shell>} />
        <Route path="/rewrites" element={<Shell><RewritePage /></Shell>} />
        <Route path="/conversations" element={<Shell><HistoryPage /></Shell>} />
      </Routes>
    </AntdApp>
  )
}
