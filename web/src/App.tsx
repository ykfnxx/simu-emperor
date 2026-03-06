import React, { useState, useRef, useEffect } from 'react';
import { createGameClient } from './api/client';
import { useWebSocket, useGameState, useAgents } from './hooks';
import type { WSMessageKind, MessageHandler, ConnectionState } from './api/types';
import {
  Plus,
  MessageSquare,
  Users,
  ChevronDown,
  ChevronRight,
  Send,
  Bot,
  TerminalSquare,
  Paperclip,
  Activity,
  Database,
  Anchor,
  ArrowRightLeft,
  History,
  Coins,
  Crown,
  Shield,
  Heart,
  Leaf,
  TrendingUp,
  AlertTriangle,
  ChevronUp,
  PanelLeft,
  PanelRight,
  Flame,
  ClipboardList,
  Clock,
  CheckCircle2,
  Loader2,
  X
} from 'lucide-react';

export default function App() {
  // 创建游戏客户端
  const client = useRef(createGameClient({
    wsUrl: 'ws://localhost:8000/ws',
    apiBaseUrl: 'http://localhost:8000/api',
  }));

  // 使用 WebSocket hook
  const {
    connectionState,
    messages,
    gameState,
    events,
    errors,
    sendChat,
    sendCommand,
    isConnected,
  } = useWebSocket(client.current);

  // 使用游戏状态 hook
  const { state: latestState } = useGameState(client.current, 5000);

  // 使用 Agents hook
  const { agents } = useAgents(client.current);

  // 基本状态管理
  const [showChatAddMenu, setShowChatAddMenu] = useState(false);
  const [agentExpanded, setAgentExpanded] = useState(true);
  const [inputText, setInputText] = useState('');
  const [isLeftPanelOpen, setIsLeftPanelOpen] = useState(true);
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(true);
  const [isTapeExpanded, setIsTapeExpanded] = useState(true);
  const [activeRightTab, setActiveRightTab] = useState('stats');

  // 记录当前选中的事件数据
  const [selectedEvent, setSelectedEvent] = useState<any>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);

  // 关闭弹窗
  const handleCloseModal = () => {
    setIsModalVisible(false);
    setTimeout(() => {
      setSelectedEvent(null);
    }, 300);
  };

  // 拖拽缩放功能
  const [leftWidth, setLeftWidth] = useState(288);
  const [rightWidth, setRightWidth] = useState(320);
  const [agentSectionHeight, setAgentSectionHeight] = useState(300);
  const [tapeHeight, setTapeHeight] = useState(320);

  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef({
    active: null as 'left' | 'right' | 'agent' | 'tape' | null,
    startY: 0,
    startHeight: 0,
  });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || !dragRef.current.active) return;

      if (dragRef.current.active === 'left') {
        const newWidth = e.clientX - 12;
        setLeftWidth(Math.max(200, Math.min(newWidth, window.innerWidth / 2)));
      }
      else if (dragRef.current.active === 'right') {
        const newWidth = window.innerWidth - e.clientX - 12;
        setRightWidth(Math.max(260, Math.min(newWidth, window.innerWidth / 2)));
      }
      else if (dragRef.current.active === 'agent') {
        const deltaY = e.clientY - dragRef.current.startY;
        const newHeight = dragRef.current.startHeight + deltaY;
        setAgentSectionHeight(Math.max(100, Math.min(newHeight, window.innerHeight - 200)));
      }
      else if (dragRef.current.active === 'tape') {
        const deltaY = dragRef.current.startY - e.clientY;
        const newHeight = dragRef.current.startHeight + deltaY;
        setTapeHeight(Math.max(150, Math.min(newHeight, window.innerHeight - 200)));
      }
    };

    const handleMouseUp = () => {
      if (isDragging) {
        setIsDragging(false);
        dragRef.current.active = null;
        document.body.style.cursor = 'default';
        document.body.style.userSelect = '';
      }
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  const handleDragStart = (active: 'left' | 'right' | 'agent' | 'tape', startY?: number, startHeight?: number) => {
    setIsDragging(true);
    dragRef.current = {
      active,
      startY: startY || 0,
      startHeight: startHeight || 0,
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  // 当前显示的 Agent（简化版）
  const [activeAgents, setActiveAgents] = useState(['governor_zhili', 'minister_of_revenue']);

  // 发送消息
  const handleSendMessage = () => {
    if (inputText.trim()) {
      // 发送给当前选中的 agent（简化：发给第一个）
      if (activeAgents.length > 0) {
        sendChat(activeAgents[0], inputText);
      }
      setInputText('');
    }
  };

  // 渲染连接状态
  const renderConnectionStatus = () => {
    if (connectionState === 'connected') {
      return (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 text-green-700 rounded-full text-xs font-medium">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          <span>已连接</span>
        </div>
      );
    } else if (connectionState === 'connecting') {
      return (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-yellow-50 text-yellow-700 rounded-full text-xs font-medium">
          <Loader2 className="w-3 h-3 animate-spin" />
          <span>连接中...</span>
        </div>
      );
    } else {
      return (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-red-50 text-red-700 rounded-full text-xs font-medium">
          <div className="w-2 h-2 bg-red-500 rounded-full" />
          <span>未连接</span>
        </div>
      );
    }
  };

  // 渲染左侧面板（Agent 列表）
  const renderLeftPanel = () => (
    <div
      className="bg-white border-r border-gray-200 flex flex-col"
      style={{ width: `${leftWidth}px` }}
    >
      {/* 头部 */}
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5 text-gray-600" />
          <h2 className="font-semibold text-gray-900">官员</h2>
        </div>
        <button
          onClick={() => setIsLeftPanelOpen(!isLeftPanelOpen)}
          className="p-1 hover:bg-gray-100 rounded"
        >
          <PanelLeft className="w-4 h-4 text-gray-600" />
        </button>
      </div>

      {/* Agent 列表 */}
      <div className="flex-1 overflow-y-auto p-2">
        {activeAgents.map((agent) => (
          <div
            key={agent}
            className="p-2 mb-1 bg-gray-50 rounded hover:bg-gray-100 cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-gray-600" />
              <span className="text-sm font-medium text-gray-900">
                {agent === 'governor_zhili' ? '直隶巡抚' : '户部尚书'}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* 拖拽手柄 */}
      <div
        className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-blue-500"
        onMouseDown={() => handleDragStart('left')}
      />
    </div>
  );

  // 渲染中间聊天区域
  const renderCenterPanel = () => (
    <div className="flex-1 flex flex-col bg-gray-50">
      {/* 顶部栏 */}
      <div className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold text-gray-900">皇帝模拟器 V2</h1>
          {renderConnectionStatus()}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsRightPanelOpen(!isRightPanelOpen)}
            className="p-2 hover:bg-gray-100 rounded"
          >
            <PanelRight className="w-4 h-4 text-gray-600" />
          </button>
        </div>
      </div>

      {/* 聊天消息区域 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* 欢迎消息 */}
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <Crown className="w-12 h-12 mx-auto mb-4 text-gray-400" />
            <p>欢迎，陛下。</p>
            <p className="text-sm">请向官员下达命令或询问政务。</p>
          </div>
        )}

        {/* 消息列表 */}
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.agent === 'player' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[70%] rounded-lg p-3 ${
                msg.agent === 'player'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white border border-gray-200'
              }`}
            >
              <div className="text-sm font-medium mb-1">
                {msg.agentDisplayName}
              </div>
              <div className="text-sm">{msg.text}</div>
            </div>
          </div>
        ))}

        {/* 错误消息 */}
        {errors.map((error, idx) => (
          <div key={idx} className="flex justify-center">
            <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm">
              {error}
            </div>
          </div>
        ))}
      </div>

      {/* 输入框 */}
      <div className="p-4 bg-white border-t border-gray-200">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="输入命令或询问政务..."
            disabled={!isConnected}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          <button
            onClick={handleSendMessage}
            disabled={!isConnected || !inputText.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
            <span>发送</span>
          </button>
        </div>
      </div>
    </div>
  );

  // 渲染右侧面板（状态或事件）
  const renderRightPanel = () => (
    <div
      className="bg-white border-l border-gray-200 flex flex-col"
      style={{ width: `${rightWidth}px` }}
    >
      {/* 头部 */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center gap-2 mb-2">
          <Database className="w-5 h-5 text-gray-600" />
          <h2 className="font-semibold text-gray-900">游戏状态</h2>
        </div>
        {gameState && (
          <div className="text-xs text-gray-600">
            回合 {gameState.turn}
          </div>
        )}
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-y-auto p-4">
        {gameState ? (
          <div className="space-y-3">
            <div className="bg-gray-50 rounded p-3">
              <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                <Coins className="w-4 h-4" />
                <span>国库</span>
              </div>
              <div className="text-lg font-semibold text-gray-900">
                {gameState.treasury.toLocaleString()} 两
              </div>
            </div>

            <div className="bg-gray-50 rounded p-3">
              <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                <Users className="w-4 h-4" />
                <span>人口</span>
              </div>
              <div className="text-lg font-semibold text-gray-900">
                {gameState.population.toLocaleString()} 人
              </div>
            </div>

            <div className="bg-gray-50 rounded p-3">
              <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                <Shield className="w-4 h-4" />
                <span>军队</span>
              </div>
              <div className="text-lg font-semibold text-gray-900">
                {gameState.military.toLocaleString()} 人
              </div>
            </div>

            <div className="bg-gray-50 rounded p-3">
              <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                <Heart className="w-4 h-4" />
                <span>民心</span>
              </div>
              <div className="text-lg font-semibold text-gray-900">
                {gameState.happiness}%
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center text-gray-500 mt-8">
            <Activity className="w-12 h-12 mx-auto mb-4 text-gray-400" />
            <p>等待游戏状态更新...</p>
          </div>
        )}
      </div>

      {/* 拖拽手柄 */}
      <div
        className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-blue-500"
        onMouseDown={() => handleDragStart('right')}
      />
    </div>
  );

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      {/* 左侧面板 */}
      {isLeftPanelOpen && renderLeftPanel()}

      {/* 中间聊天区域 */}
      {renderCenterPanel()}

      {/* 右侧面板 */}
      {isRightPanelOpen && renderRightPanel()}
    </div>
  );
}
