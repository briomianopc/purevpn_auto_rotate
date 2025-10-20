#!/usr/bin/env python3
import os, sys, time, random, subprocess, logging, re, json, requests
from pathlib import Path

# ============ 配置部分 ============
CONFIG_DIR = "/opt/purevpn_auto_rotate/configs"
TEMPLATE_CONFIG = "/opt/purevpn_auto_rotate/base.ovpn"
LOG_FILE = "/opt/purevpn_auto_rotate/logs/openvpn_rotate.log"
ROTATE_INTERVAL = 3600  # 1小时
PUBLIC_IP_API = "https://ipinfo.io/json"
CREDS_FILE = "/opt/purevpn_auto_rotate/creds.txt"

SERVERS = [
    # 美国节点
    ("us2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("us2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    ("usca2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("usca2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    ("usfl2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("usfl2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    ("usny2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("usny2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    ("ustx2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("ustx2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    
    # 卢森堡节点
    ("lu2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("lu2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    
    # 东南亚节点
    ("sg2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("sg2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    ("hk2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("hk2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    ("ph2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("ph2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    ("vn2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("vn2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    
    # 日本节点
    ("jp2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("jp2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    
    # 韩国节点
    ("kr2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("kr2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    
    # 澳洲节点
    ("au2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("au2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    ("aupe2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("aupe2-auto-udp-qr.ptoserver.com", 1194, "udp"),
    ("ausd2-auto-tcp-qr.ptoserver.com", 80, "tcp"),
    ("ausd2-auto-udp-qr.ptoserver.com", 1194, "udp"),
]

# ============ 日志 ============
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ============ 工具函数 ============

def read_template():
    with open(TEMPLATE_CONFIG, "r") as f:
        return f.read()

def replace_remote(content, host, port, proto):
    c = re.sub(r"remote\s+[\w\-.]+\s+\d+", f"remote {host} {port}", content)
    c = re.sub(r"proto\s+\w+", f"proto {proto}", c)
    
    # 确保用正确的路径指向认证文件
    if f"auth-user-pass {CREDS_FILE}" not in c:
        c = re.sub(r"auth-user-pass\s*\n?", f"auth-user-pass {CREDS_FILE}\n", c)
    
    # ===== 关键修复：删除全局路由 =====
    # 删除 "route 0.0.0.0 0.0.0.0" 防止SSH被劫持
    c = re.sub(r"^route\s+0\.0\.0\.0\s+0\.0\.0\.0\s*$", "", c, flags=re.MULTILINE)
    
    # 禁用服务器推送的全局路由
    if "pull-filter ignore \"redirect-gateway\"" not in c:
        c += "\npull-filter ignore \"redirect-gateway\"\n"
    
    if "route-nopull" not in c:
        c += "route-nopull\n"
    
    if "persist-tun" not in c:
        c += "persist-tun\n"
    
    return c

def write_config(config, name):
    path = Path(CONFIG_DIR) / f"{name}.conf"
    with open(path, "w") as f:
        f.write(config)
    os.chmod(path, 0o600)
    return path

def stop_vpn():
    """杀死所有OpenVPN进程"""
    subprocess.run(["sudo", "pkill", "-9", "openvpn"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)

def start_vpn(cfg_path):
    """以前台模式启动OpenVPN，使用systemd管理"""
    # 提取配置名称
    cfg_name = cfg_path.stem
    
    # 创建systemd service文件
    service_content = f"""[Unit]
Description=OpenVPN {cfg_name}
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/sbin/openvpn --config {cfg_path} --suppress-timestamps
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    
    service_path = f"/etc/systemd/system/openvpn@{cfg_name}.service"
    
    try:
        with open(service_path, "w") as f:
            f.write(service_content)
        
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        subprocess.run(["sudo", "systemctl", "restart", f"openvpn@{cfg_name}"], check=True)
        time.sleep(10)  # 等待TUN接口创建
        
    except Exception as e:
        log.error(f"启动OpenVPN失败: {e}")
        return False
    
    return True

def check_tun_interface():
    """检查TUN接口是否存在"""
    result = subprocess.run(["ip", "link", "show", "tun0"], capture_output=True)
    return result.returncode == 0

def get_ip():
    try:
        r = requests.get(PUBLIC_IP_API, timeout=6)
        if r.status_code == 200:
            data = r.json()
            return data.get("ip", "?"), data.get("country", "?")
    except:
        return "unknown", "?"
    return "unknown", "?"

# ============ 主循环 ============

def main():
    tpl = read_template()
    log.info("="*60)
    log.info("PureVPN 自动轮换启动")
    log.info(f"共 {len(SERVERS)} 个节点，轮换间隔 {ROTATE_INTERVAL//60} 分钟")
    log.info("="*60)

    while True:
        node = random.choice(SERVERS)
        host, port, proto = node
        name = host.split(".")[0]
        cfg = replace_remote(tpl, host, port, proto)
        cfg_path = write_config(cfg, name)

        stop_vpn()
        
        if start_vpn(cfg_path):
            # 检查TUN接口
            if check_tun_interface():
                log.info(f"TUN接口已创建: tun0")
            else:
                log.warning("警告: TUN接口未检测到")
            
            ip, country = get_ip()
            if ip != "unknown":
                log.info(f"成功连接 {host}:{port} ({proto.upper()}) -> {ip} [{country}]")
            else:
                log.warning(f"连接失败或IP查询失败 {host}:{port} ({proto.upper()})")
        else:
            log.warning(f"连接失败 {host}:{port} ({proto.upper()})")
        
        log.info(f"等待 {ROTATE_INTERVAL//60} 分钟后切换...")
        time.sleep(ROTATE_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("用户中断")
        stop_vpn()
