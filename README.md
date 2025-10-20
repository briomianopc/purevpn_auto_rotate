# PureVPN 自动IP轮换脚本

一个自动轮换PureVPN连接节点的Python脚本，每小时随机切换一个VPN出口IP，支持通过TUN接口隔离VPN流量。

## 功能特性

- **自动轮换IP**：每1小时随机选择一个节点并切换连接
- **支持TCP/UDP**：智能选择TCP (端口80) 或 UDP (端口1194) 协议
- **地理位置多样**：覆盖美国、卢森堡、东南亚、日本、韩国、澳洲等地
- **TUN隔离模式**：仅VPN流量走TUN接口，SSH等本地连接不受影响
- **安全路由**：自动删除全局路由配置，防止SSH被劫持
- **完整日志**：记录每次切换的时间、节点、出口IP和地理位置

## 系统要求

- Linux (Ubuntu/Debian 推荐)
- Python 3.6+
- OpenVPN 已安装
- sudo 权限
- 网络连接

## 安装步骤

### 1. 创建工作目录

```bash
sudo mkdir -p /opt/purevpn_auto_rotate/{configs,logs}
sudo chown $USER:$USER /opt/purevpn_auto_rotate
```

### 2. 获取PureVPN配置文件

从PureVPN官网下载你的 `.ovpn` 配置文件，并重命名为 `base.ovpn`：

```bash
cp /path/to/your/config.ovpn /opt/purevpn_auto_rotate/base.ovpn
```

### 3. 创建认证文件

新建 `creds.txt` 文件，第一行是用户名，第二行是密码：

```bash
cat > /opt/purevpn_auto_rotate/creds.txt << EOF
your_username
your_password
EOF

chmod 600 /opt/purevpn_auto_rotate/creds.txt
```

### 4. 安装Python依赖

```bash
pip3 install requests
```

### 5. 部署脚本

将脚本保存为 `/opt/purevpn_auto_rotate/rotate.py`：

```bash
chmod +x /opt/purevpn_auto_rotate/rotate.py
```

## 使用方法

### 前台运行（用于测试）

```bash
sudo python3 /opt/purevpn_auto_rotate/rotate.py
```

### 后台运行（使用nohup）

```bash
sudo nohup python3 /opt/purevpn_auto_rotate/rotate.py > /opt/purevpn_auto_rotate/logs/rotate.log 2>&1 &
```

### 作为系统服务运行（推荐）

创建 systemd service 文件：

```bash
sudo tee /etc/systemd/system/purevpn-rotate.service > /dev/null << EOF
[Unit]
Description=PureVPN Auto Rotate Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/purevpn_auto_rotate/rotate.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

启用并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable purevpn-rotate.service
sudo systemctl start purevpn-rotate.service
```

### 管理命令

```bash
# 查看服务状态
sudo systemctl status purevpn-rotate.service

# 查看实时日志
sudo journalctl -u purevpn-rotate.service -f

# 停止服务
sudo systemctl stop purevpn-rotate.service

# 重启服务
sudo systemctl restart purevpn-rotate.service
```

## 验证工作

### 1. 检查TUN接口

```bash
ip link show tun0
```

应该看到类似输出：
```
4: tun0: <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> mtu 1500
```

### 2. 测试VPN流量

查看通过TUN接口的出口IP：

```bash
curl --interface tun0 -s https://ipinfo.io/json | jq '.ip, .country'
```

### 3. 验证SSH不受影响

确保SSH连接仍然正常：

```bash
ssh user@your_server
```

### 4. 查看日志

```bash
tail -f /opt/purevpn_auto_rotate/logs/openvpn_rotate.log
```

日志输出示例：
```
[2024-01-15 10:30:45] ============================================================
[2024-01-15 10:30:45] PureVPN 自动轮换启动
[2024-01-15 10:30:45] 共 30 个节点，轮换间隔 60 分钟
[2024-01-15 10:30:45] ============================================================
[2024-01-15 10:35:50] TUN接口已创建: tun0
[2024-01-15 10:35:52] 成功连接 sg2-auto-tcp-qr.ptoserver.com:80 (TCP) -> 1.2.3.4 [SG]
[2024-01-15 10:35:53] 等待 60 分钟后切换...
```

## 节点列表

脚本包含以下30个节点（随机轮换）：

- **美国** (10个): 通用、加州、佛州、纽约、德州
- **卢森堡** (2个): 欧洲数据中心
- **东南亚** (8个): 新加坡、香港、菲律宾、越南
- **日本** (2个): 东亚地区
- **韩国** (2个): 东亚地区
- **澳洲** (6个): 悉尼、珀斯等地区

## 配置调整

### 修改轮换间隔

编辑脚本中的 `ROTATE_INTERVAL`：

```python
ROTATE_INTERVAL = 3600  # 改为其他值（单位：秒）
# 例如：300 = 5分钟，1800 = 30分钟，7200 = 2小时
```

### 修改日志位置

编辑脚本中的 `LOG_FILE`：

```python
LOG_FILE = "/opt/purevpn_auto_rotate/logs/openvpn_rotate.log"
```

## 故障排除

### 问题1：SSH连接断联

**原因**：配置中的 `route 0.0.0.0 0.0.0.0` 导致全局路由被劫持

**解决**：脚本已自动删除此行。如果仍有问题：

```bash
# 手动清理路由
sudo ip route flush all
sudo systemctl restart networking
```

### 问题2：TUN接口未创建

**检查**：
```bash
ip link show tun0
```

**解决**：
- 确保 OpenVPN 已安装：`which openvpn`
- 等待更长时间（脚本已设置10秒等待）
- 检查 OpenVPN 进程：`ps aux | grep openvpn`

### 问题3：VPN连接失败

**检查日志**：
```bash
sudo journalctl -u purevpn-rotate.service -n 50
```

**可能原因**：
- PureVPN 账户过期或无效
- 网络连接问题
- 节点服务器离线

### 问题4：IP查询失败

如果 `ipinfo.io` 不可用，修改脚本中的 `PUBLIC_IP_API`：

```python
PUBLIC_IP_API = "https://api.ipify.org"  # 或其他IP查询服务
```

## 安全建议

1. **保护认证文件**
```bash
sudo chmod 600 /opt/purevpn_auto_rotate/creds.txt
```

2. **定期检查日志**
```bash
sudo tail -f /opt/purevpn_auto_rotate/logs/openvpn_rotate.log
```

3. **验证SSH连接**
每次轮换后都要测试SSH是否仍然可用

4. **备份配置**
```bash
cp /opt/purevpn_auto_rotate/base.ovpn /opt/purevpn_auto_rotate/base.ovpn.bak
```

## 许可证

MIT License(https://github.com/briomianopc/purevpn_auto_rotate/blob/main/LICENSE)

## 支持

如有问题或建议，请查看日志文件获取更多信息。
