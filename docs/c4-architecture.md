# 即時聊天室系統 - C4 架構文檔

## 目錄

1. [系統概述](#系統概述)
2. [C1 - 系統上下文](#c1---系統上下文)
3. [C2 - 容器架構](#c2---容器架構)
4. [C3 - 組件架構](#c3---組件架構)
5. [C4 - 程式碼架構](#c4---程式碼架構)
6. [資料流架構](#資料流架構)

---

## 系統概述

**系統名稱**: 即時多人聊天室系統

**系統描述**: 基於 FastAPI + MongoDB + SvelteKit 的即時通訊平台，支援多房間、檔案分享、即時通知等功能。

**技術架構**: 三層架構 + 依賴注入 + 記憶體WebSocket廣播架構

**部署方式**: Docker容器化部署，單實例限制

---

## C1 - 系統上下文

### 系統邊界圖

```mermaid
graph TB
    subgraph "系統邊界"
        ChatSystem[即時聊天室系統<br/>Chat Room System]
    end

    User[使用者<br/>Users]
    Admin[系統管理員<br/>System Admin]

    subgraph "外部系統"
        MongoDB[(MongoDB<br/>文件資料庫)]
        Redis[(Redis<br/>快取層)]
        FileStorage[本地檔案系統<br/>uploads 目錄]
    end

    User -->|使用| ChatSystem
    Admin -->|管理| ChatSystem

    ChatSystem -->|讀寫| MongoDB
    ChatSystem -->|快取| Redis
    ChatSystem -->|儲存| FileStorage

    style ChatSystem fill:#f9f,stroke:#333
    style User fill:#bbf,stroke:#333
    style Admin fill:#bbf,stroke:#333
    style MongoDB fill:#9f9,stroke:#333
    style Redis fill:#9f9,stroke:#333
    style FileStorage fill:#ff9,stroke:#333
```

### 關係說明

| 參與者 | 與系統關係 | 通訊協議 | 資料類型 |
|--------|------------|----------|----------|
| **使用者** | 使用聊天功能 | HTTPS, WebSocket | 聊天訊息、檔案 |
| **管理員** | 系統管理、監控 | HTTPS | 管理操作、系統配置 |
| **MongoDB** | 持久化儲存 | TCP/IP | 用戶資料、訊息記錄、房間資料 |
| **Redis** | 快取層 | TCP/IP | 快取資料、速率限制 |
| **檔案儲存** | 本地檔案儲存 | 檔案系統 | 圖片、文件、媒體檔案 |

---

## C2 - 容器架構

### 容器部署圖

```mermaid
graph TB
    subgraph "即時聊天室系統"
        Frontend[前端應用<br/>SvelteKit SPA<br/>容器: Node.js<br/>端口: 5173]
        Backend[後端 API + WebSocket<br/>FastAPI<br/>容器: Python<br/>端口: 8000]

        subgraph "基礎設施服務"
            MongoDB[(MongoDB<br/>文件資料庫<br/>端口: 27017)]
            Redis[(Redis<br/>快取層<br/>端口: 6379)]
            FileStorage[檔案儲存<br/>本地檔案系統<br/>uploads 目錄]
        end
    end

    User[使用者瀏覽器<br/>Chrome/Safari/Firefox]

    User -->|HTTPS:5173| Frontend
    Frontend -->|REST API:8000| Backend
    Frontend -->|WebSocket:8000/ws| Backend

    Backend -->|TCP:27017| MongoDB
    Backend -->|TCP:6379| Redis
    Backend -->|檔案系統| FileStorage

    Backend -->|記憶體廣播| ConnectionManager[內建連線管理器]

    style Frontend fill:#90EE90
    style Backend fill:#87CEEB
    style MongoDB fill:#F0E68C
    style Redis fill:#F0E68C
    style FileStorage fill:#F0E68C
```

### 容器技術規格

| 容器 | 技術堆疊 | 主要功能 | 擴展性 |
|------|----------|----------|--------|
| **前端** | SvelteKit + TypeScript + DaisyUI | 用戶界面、路由、狀態管理 | 水平擴展 |
| **後端 API + WebSocket** | FastAPI + Python + uvicorn | REST API、WebSocket、業務邏輯 | 單實例（記憶體廣播限制） |
| **MongoDB** | MongoDB | 資料持久化  | 垂直擴展 |
| **Redis** | Redis | 快取層、速率限制  | 垂直擴展 |

---

## C3 - 組件架構

### 3.1 後端 API 組件架構

#### 展示層組件

```mermaid
graph TB
    subgraph "展示層 (Presentation Layer)"
        AuthRouter[認證路由<br/>/api/auth<br/>POST /login, /register]
        RoomRouter[房間路由<br/>/api/rooms<br/>GET /rooms, POST /rooms]
        MessageRouter[訊息路由<br/>/api/messages<br/>GET /messages, POST /messages]
        FileRouter[檔案路由<br/>/api/files<br/>POST /upload, GET /image]
        NotificationRouter[通知路由<br/>/api/notifications<br/>GET /notifications]
        InvitationRouter[邀請路由<br/>/api/invitations<br/>POST /create, GET /validate]
    end

    subgraph "中介層 (Middleware)"
        CORSMiddleware[CORS中介軟體<br/>跨域請求處理]
        AuthMiddleware[認證中介軟體<br/>JWT Token驗證]
        RateLimiter[速率限制器<br/>API請求限制]
        ErrorHandler[錯誤處理器<br/>全域錯誤處理]
        SecurityHeaders[安全標頭<br/>安全相關HTTP標頭]
    end

    AuthRouter --> AuthMiddleware
    RoomRouter --> AuthMiddleware
    MessageRouter --> AuthMiddleware
    FileRouter --> AuthMiddleware
    NotificationRouter --> AuthMiddleware
    InvitationRouter --> AuthMiddleware

    CORSMiddleware -.->|全域| AllRoutes[所有路由]
    RateLimiter -.->|全域| AllRoutes

    style AuthRouter fill:#FFB6C1
    style RoomRouter fill:#FFB6C1
    style MessageRouter fill:#FFB6C1
    style FileRouter fill:#FFB6C1
    style NotificationRouter fill:#FFB6C1
    style InvitationRouter fill:#FFB6C1
```

#### 業務層組件

```mermaid
graph TB
    subgraph "業務層 (Business Layer)"
        UserService[用戶服務<br/>UserService<br/>用戶資料管理]
        RoomService[房間服務<br/>RoomService<br/>房間創建/管理]
        MessageService[訊息服務<br/>MessageService<br/>訊息處理]
        NotificationService[通知服務<br/>NotificationService<br/>系統通知]
        InvitationService[邀請服務<br/>InvitationService<br/>邀請碼管理]
    end

    subgraph "服務依賴關係"
        UserService --> UserRepo[UserRepository]
        RoomService --> RoomRepo[RoomRepository]
        MessageService --> MessageRepo[MessageRepository]
        NotificationService --> NotificationRepo[NotificationRepository]
        InvitationService --> RoomRepo
    end

    subgraph "跨領域服務"
        CacheManager[快取管理器<br/>CacheManager<br/>Redis操作]
        FileUploadManager[檔案上傳管理<br/>FileUploadManager<br/>檔案處理]
        ImageProcessor[圖片處理器<br/>ImageProcessor<br/>縮圖生成]
        PasswordHasher[密碼處理<br/>PasswordHasher<br/>密碼加密驗證]
        JWTHandler[JWT處理<br/>JWTHandler<br/>Token生成驗證]
    end

    UserService --> PasswordHasher
    UserService --> JWTHandler
    RoomService --> CacheManager
    MessageService --> CacheManager
    MessageService --> FileUploadManager

    style UserService fill:#98FB98
    style RoomService fill:#98FB98
    style MessageService fill:#98FB98
    style NotificationService fill:#98FB98
    style InvitationService fill:#98FB98
```

#### 資料層組件

```mermaid
graph TB
    subgraph "資料層 (Data Layer)"
        UserRepository[用戶倉儲<br/>UserRepository<br/>用戶資料CRUD]
        RoomRepository[房間倉儲<br/>RoomRepository<br/>房間資料CRUD]
        MessageRepository[訊息倉儲<br/>MessageRepository<br/>訊息資料CRUD]
        NotificationRepository[通知倉儲<br/>NotificationRepository<br/>通知資料CRUD]
    end

    subgraph "資料存取層"
        MongoDBManager[MongoDB管理器<br/>MongoDBManager<br/>資料庫連線管理]
        RedisManager[Redis管理器<br/>RedisManager<br/>快取連線管理]
        FileSystem[檔案系統<br/>本地儲存<br/>uploads目錄]
    end

    subgraph "資料模型"
        UserModel[用戶模型<br/>User]
        RoomModel[房間模型<br/>Room]
        MessageModel[訊息模型<br/>Message]
        NotificationModel[通知模型<br/>Notification]
        InvitationModel[邀請模型<br/>Invitation]
    end

    UserRepository --> MongoDBManager
    RoomRepository --> MongoDBManager
    MessageRepository --> MongoDBManager
    NotificationRepository --> MongoDBManager

    UserRepository --> UserModel
    RoomRepository --> RoomModel
    MessageRepository --> MessageModel
    NotificationRepository --> NotificationModel

    style UserRepository fill:#87CEFA
    style RoomRepository fill:#87CEFA
    style MessageRepository fill:#87CEFA
    style NotificationRepository fill:#87CEFA
```

### 3.2 WebSocket 伺服器組件架構

```mermaid
graph TB
    subgraph "WebSocket 伺服器組件"
        subgraph "連線管理"
            WebSocketRouter["WebSocket路由<br/>/ws/{room_id}"<br/>訊息路由]
            WebSocketAuth[WebSocket認證<br/>JWT Token驗證]
            ConnectionManager[連線管理器<br/>ConnectionManager<br/>WebSocket連線管理]
        end

        subgraph "訊息處理"
            MessageHandler[訊息處理器<br/>handle_message<br/>訊息處理邏輯]
            JoinHandler[加入處理器<br/>handle_join<br/>加入房間邏輯]
            LeaveHandler[離開處理器<br/>handle_leave<br/>離開房間邏輯]
            TypingHandler[輸入狀態處理器<br/>handle_typing<br/>輸入狀態同步]
            ReadStatusHandler[已讀狀態處理器<br/>handle_read_status<br/>已讀狀態同步]
        end

        subgraph "即時通訊層"
            MemoryBroadcast[記憶體廣播<br/>broadcast_to_room<br/>單實例廣播]
            UserPresence[線上狀態管理<br/>track_user_presence<br/>用戶線上狀態]
            RoomUsers[房間用戶管理<br/>room_users<br/>房間成員追蹤]
        end
    end

    WebSocketRouter --> WebSocketAuth
    WebSocketAuth --> ConnectionManager

    ConnectionManager --> MessageHandler
    ConnectionManager --> JoinHandler
    ConnectionManager --> LeaveHandler
    ConnectionManager --> TypingHandler
    ConnectionManager --> ReadStatusHandler

    MessageHandler --> MemoryBroadcast
    JoinHandler --> RoomUsers
    LeaveHandler --> RoomUsers
    TypingHandler --> MemoryBroadcast
    ReadStatusHandler --> MemoryBroadcast

    UserPresence --> ConnectionManager

    style ConnectionManager fill:#DDA0DD
    style MessageHandler fill:#98FB98
    style MemoryBroadcast fill:#F0E68C
```

### 3.3 前端組件架構

```mermaid
graph TB
    subgraph "前端組件架構"
        subgraph "路由層"
            Layout[+layout.svelte<br/>主佈局組件]
            Home[+page.svelte<br/>首頁組件]
            Login[login/+page.svelte<br/>登入頁組件]
            Register[register/+page.svelte<br/>註冊頁組件]
            Room["room/[id]/+page.svelte"<br/>聊天室組件]
            Rooms[rooms/+page.svelte<br/>房間列表組件]
            Profile[profile/+page.svelte<br/>個人資料組件]
            Dashboard[dashboard/+page.svelte<br/>儀表板組件]
        end

        subgraph "狀態管理 (Svelte 5 Runes)"
            AuthStore[認證狀態<br/>auth.svelte.ts<br/>用戶認證狀態]
            RoomStore[房間狀態<br/>room.svelte.ts<br/>房間資料管理]
            MessageStore[訊息狀態<br/>message.svelte.ts<br/>訊息資料管理]
            NotificationStore[通知狀態<br/>notification.svelte.ts<br/>通知管理]
            NetworkStore[網路狀態<br/>networkStatus.svelte.ts<br/>網路連線監控]
            ErrorStore[錯誤狀態<br/>errorHandler.svelte.ts<br/>錯誤處理]
        end

        subgraph "API層"
            BFFClient[BFF客戶端<br/>bff-client.ts<br/>Backend for Frontend]
            WebSocketManager[WebSocket管理器<br/>manager.ts<br/>WebSocket連線管理]
            APIClient[API客戶端<br/>client.ts<br/>REST API封裝]
        end

        subgraph "UI組件層"
            MessageList[MessageList<br/>訊息列表組件]
            MessageInput[MessageInput<br/>輸入框組件]
            MessageItem[MessageItem<br/>單一訊息組件]
            UserList[UserList<br/>線上用戶列表]
            RoomList[RoomList<br/>房間列表]
            RoomHeader[RoomHeader<br/>房間標題]
            FileUpload[FileUpload<br/>檔案上傳組件]
            ImageViewer[ImageViewer<br/>圖片檢視器]
            NotificationPanel[NotificationPanel<br/>通知面板]
        end

        subgraph "工具層"
            DateTimeUtils[日期時間工具<br/>datetime.ts<br/>時間格式化]
            ErrorHandler[錯誤處理<br/>error-handler.ts<br/>全域錯誤處理]
            RetryLogic[重試邏輯<br/>retry.ts<br/>請求重試機制]
            NotificationSound[通知音效<br/>notificationSound.ts<br/>音效播放]
        end
    end

    Layout --> AuthStore
    Room --> MessageStore
    Room --> RoomStore
    Room --> WebSocketManager

    MessageList --> MessageStore
    MessageInput --> WebSocketManager
    UserList --> RoomStore

    BFFClient --> APIClient
    WebSocketManager --> NetworkStore
    APIClient --> ErrorHandler

    style Layout fill:#FFB6C1
    style AuthStore fill:#98FB98
    style BFFClient fill:#87CEFA
    style MessageList fill:#DDA0DD
```

---

## C4 - 程式碼架構

### 4.1 依賴注入容器實現

#### 容器類別結構

```mermaid
classDiagram
    class DIContainer {
        -services: dict[type, ServiceDescriptor]
        -instances: dict[type, Any]
        -scoped_instances: dict[str, dict[type, Any]]
        -lock: asyncio.Lock
        +register_singleton(service_type, implementation_type, factory, instance)
        +register_scoped(service_type, implementation_type, factory)
        +register_transient(service_type, implementation_type, factory)
        +get(service_type, scope_id) Any
        +clear_scope(scope_id)
        +clear_all_scopes()
    }

    class ServiceDescriptor {
        +service_type: type
        +implementation_type: type
        +factory: Callable
        +instance: Any
        +lifetime: ServiceLifetime
        +__init__(service_type, implementation_type, factory, instance, lifetime)
    }

    class ServiceLifetime {
        <<enumeration>>
        SINGLETON
        SCOPED
        TRANSIENT
    }

    class UserService {
        -user_repo: UserRepository
        -room_repo: RoomRepository
        -message_repo: MessageRepository
        +create_user(user_data) User
        +get_user_profile(user_id) User
        +update_user(user_id, update_data) User
        +delete_user(user_id) bool
    }

    class UserRepository {
        -db: AsyncDatabase
        -collection: Collection
        +create(user) User
        +find_by_id(user_id) User
        +find_by_username(username) User
        +update(user_id, update_data) User
        +delete(user_id) bool
        +find_all(skip, limit) List[User]
    }

    DIContainer --> ServiceDescriptor
    ServiceDescriptor --> ServiceLifetime
    UserService --> UserRepository

    class FastAPIIntegration {
        +setup_dependency_injection(app)
        +create_dependency_factory(service_type)
        +cleanup_dependency_injection(app)
        +request_scope_middleware(request, call_next)
    }
```

### 4.2 WebSocket 訊息處理流程（記憶體廣播）

#### 序列圖 - 訊息發送流程

```mermaid
sequenceDiagram
    participant Client as 瀏覽器客戶端
    participant WS as WebSocket伺服器
    participant Handler as MessageHandler
    participant Service as MessageService
    participant Repo as MessageRepository
    participant Manager as ConnectionManager
    participant Mongo as MongoDB

    Client->>WS: 發送訊息 {"type": "message", "content": "Hello"}
    WS->>Handler: 路由到MessageHandler
    Handler->>Service: 呼叫MessageService.create_message()
    Service->>Repo: 儲存訊息到資料庫
    Repo->>Mongo: insert_one(message_data)
    Mongo-->>Repo: 返回儲存結果
    Repo-->>Service: 返回訊息物件
    Service-->>Handler: 返回建立的訊息
    Handler->>Manager: broadcast_to_room(room_id, message)
    Manager->>Manager: 遍歷記憶體中的連線
    Manager->>Client: 推送訊息給房間內所有用戶

    Note over Service: 業務邏輯處理<br/>- 權限驗證<br/>- 訊息格式化<br/>- 資料驗證
    Note over Manager: 記憶體廣播<br/>- 單實例限制<br/>- 低延遲
```

### 4.3 認證流程程式碼層級

#### 認證序列圖

```mermaid
sequenceDiagram
    participant User as 使用者
    participant Frontend as 前端(SvelteKit)
    participant BFF as BFF Layer
    participant API as FastAPI後端
    participant AuthDep as AuthDependency
    participant UserRepo as UserRepository
    participant JWT as JWTHandler
    participant Mongo as MongoDB

    User->>Frontend: 輸入登入資訊
    Frontend->>BFF: POST /api/auth/login
    BFF->>API: POST /api/auth/login
    API->>AuthDep: get_current_user_by_credentials
    AuthDep->>UserRepo: find_by_username(username)
    UserRepo->>Mongo: find_one({"username": username})
    Mongo-->>UserRepo: 返回用戶資料
    UserRepo-->>AuthDep: 返回用戶物件
    AuthDep->>AuthDep: verify_password(password, hashed)

    alt 驗證成功
        AuthDep->>JWT: create_access_token(user_data)
        JWT-->>AuthDep: 返回JWT Token
        AuthDep-->>API: 返回用戶和Token
        API-->>BFF: 200 OK + Token
        BFF-->>Frontend: 設置Cookie + 返回用戶資料
        Frontend->>Frontend: 更新認證狀態
    else 驗證失敗
        AuthDep-->>API: 拋出401異常
        API-->>BFF: 401 Unauthorized
        BFF-->>Frontend: 401錯誤
        Frontend->>Frontend: 顯示錯誤訊息
    end
```

---

## 資料流架構

### 資料流圖

```mermaid
graph LR
    subgraph "資料來源"
        UserInput[用戶輸入]
        WebSocketMsg[WebSocket訊息]
        FileUpload[檔案上傳]
    end

    subgraph "資料處理層"
        Validation[資料驗證]
        BusinessLogic[業務邏輯]
        FileProcessor[檔案處理]
    end

    subgraph "資料儲存層"
        MongoDB[(MongoDB)]
        Redis[(Redis快取)]
        LocalFS[本地檔案系統]
    end

    subgraph "資料輸出"
        WebSocketPush[WebSocket推送]
        RESTAPI[REST API回應]
        FileServe[檔案服務]
    end

    UserInput --> Validation
    WebSocketMsg --> BusinessLogic
    FileUpload --> FileProcessor

    Validation --> MongoDB
    BusinessLogic --> Redis
    BusinessLogic --> MongoDB
    FileProcessor --> LocalFS
    FileProcessor --> MongoDB

    MongoDB --> WebSocketPush
    Redis --> RESTAPI
    LocalFS --> FileServe

    style UserInput fill:#bbf
    style MongoDB fill:#9f9
    style WebSocketPush fill:#ff9
```

---

## 架構決策記錄 (ADR)

### ADR-001: 技術堆疊選擇

**狀態**: 已實作
**決策**: 使用 FastAPI + MongoDB + SvelteKit 技術堆疊
**原因**:

- FastAPI: 高效能、自動API文檔、類型安全、內建WebSocket支援
- MongoDB: 文件資料庫、靈活Schema、易於開發
- SvelteKit: 編譯時優化、響應式、輕量級、內建路由

### ADR-002: 架構模式

**狀態**: 已實作
**決策**: 採用三層架構 + 依賴注入模式
**原因**:

- 分離關注點，提高可維護性
- 支援單元測試和整合測試
- 降低耦合度，提高可擴展性
- 依賴注入容器實現服務生命週期管理

### ADR-003: 即時通訊方案

**狀態**: 已實作
**決策**: WebSocket + 記憶體廣播架構
**原因**:

- WebSocket: 雙向即時通訊，低延遲
- 記憶體廣播: 實作簡單、效能優異
- 單實例限制: 適合中小型應用，避免複雜性
- 未來擴展: 可改為Redis Pub/Sub實現水平擴展

### ADR-004: 檔案儲存策略

**狀態**: 已實作
**決策**: 本地檔案系統儲存
**原因**:

- 實作簡單，無需外部服務
- 適合開發和小型部署
- 檔案通過FastAPI端點服務
- 未來可遷移至S3或其他雲端儲存

### ADR-005: 前端狀態管理

**狀態**: 已實作
**決策**: Svelte 5 Runes + BFF模式
**原因**:

- Svelte 5 Runes: 新的響應式系統，更好的TypeScript支援
- BFF (Backend for Frontend): 簡化前端邏輯，統一API介面
- 減少前端複雜度，提升開發效率

---

## 系統限制與未來改進

### 目前限制

1. **單實例限制**: WebSocket使用記憶體廣播，無法水平擴展
2. **檔案儲存**: 本地儲存限制了多實例部署
3. **缺少外部服務**: 無郵件服務、推播通知等功能

### 未來改進方向

1. **水平擴展**: 實作Redis Pub/Sub替代記憶體廣播
2. **雲端儲存**: 整合S3或其他物件儲存服務
3. **外部服務整合**: 加入郵件、推播等通知服務
4. **API版本控制**: 加入/api/v1前綴支援版本管理
5. **完整容器化**: 將前後端應用加入docker-compose

---
