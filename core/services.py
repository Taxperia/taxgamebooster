import win32service
import win32serviceutil
import win32con
from dataclasses import dataclass
import wmi

SAFE_STOP_SUGGESTIONS = {
    "DiagTrack": "Connected User Experiences and Telemetry",
    "WSearch": "Windows Search",
    "SysMain": "Superfetch / SysMain",
    "Fax": "Fax",
    "WbioSrvc": "Windows Biometric Service",
    "WerSvc": "Windows Error Reporting Service",
    "MapsBroker": "Downloaded Maps Manager",
}

CRITICAL_PREFIXES = ("WinDefend", "Lanman", "EventLog", "Audio", "Time", "PlugPlay", "RpcSs", "DcomLaunch", "Dhcp", "DNS", "IKEEXT")

@dataclass
class ServiceInfo:
    name: str
    display_name: str
    status: str  # RUNNING, STOPPED, ...
    can_stop: bool

def list_services() -> list[ServiceInfo]:
    sc_handle = win32service.OpenSCManager(None, None, win32con.GENERIC_READ)
    try:
        statuses = win32service.EnumServicesStatus(sc_handle)
        out: list[ServiceInfo] = []
        for (name, display, status) in statuses:
            state = status[1]
            state_str = {
                win32service.SERVICE_STOPPED: "STOPPED",
                win32service.SERVICE_START_PENDING: "START_PENDING",
                win32service.SERVICE_STOP_PENDING: "STOP_PENDING",
                win32service.SERVICE_RUNNING: "RUNNING",
                win32service.SERVICE_CONTINUE_PENDING: "CONTINUE_PENDING",
                win32service.SERVICE_PAUSE_PENDING: "PAUSE_PENDING",
                win32service.SERVICE_PAUSED: "PAUSED",
            }.get(state, "UNKNOWN")
            can_stop = not name.startswith(CRITICAL_PREFIXES)
            out.append(ServiceInfo(name=name, display_name=display, status=state_str, can_stop=can_stop))
        return out
    finally:
        win32service.CloseServiceHandle(sc_handle)

def stop_service(name: str) -> bool:
    try:
        win32serviceutil.StopService(name)
        return True
    except Exception as e:
        print("stop_service error:", e)
        return False

def get_service_description(name: str) -> str:
    try:
        c = wmi.WMI()
        for s in c.Win32_Service(Name=name):
            desc = s.Description or ""
            return desc.strip()
    except Exception:
        pass
    return SAFE_STOP_SUGGESTIONS.get(name, "Açıklama bulunamadı.")