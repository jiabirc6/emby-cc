# Emby-CC

Emby Community Care - Emby 签到与保活工具。

## 功能

- **签到** — Telegram Bot 自动签到 + Emby 站点签到
- **保活** — Emby 账号播放模拟，防止账号被回收
- 多账号管理、自动重试、Docker 部署

## 快速开始

### 安装

```bash
pip install emby-cc
```

### 配置

复制示例配置文件并编辑：

```bash
cp config.example.toml config.toml
# 编辑 config.toml 填入你的 Emby 服务器信息
```

### 运行

```bash
# 启动签到和保活服务
emby-cc run

# 仅执行签到
emby-cc checkin

# 仅执行保活
emby-cc keepalive

# 查看状态
emby-cc status
```

### Docker

```bash
cd docker
docker-compose up -d
```

## 开发

```bash
git clone https://github.com/jiabirc6/emby-cc.git
cd emby-cc
pip install -e ".[dev]"
pytest
```

## License

MIT
