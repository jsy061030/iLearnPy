"""
iLearn Video Downloader and Player

This module provides functionality to authenticate with JLU's iLearn platform,
retrieve course information, and play classroom recordings.
"""

from typing import Any, Optional, List, Dict, Tuple
import requests
import os
import sys
import subprocess
import json
import urllib.parse
import time
import base64
import getpass
from multiprocessing import Process
from bs4 import BeautifulSoup
from requests.cookies import create_cookie

import des

# ============================================================================
# Constants
# ============================================================================

# URLs
CAS_URL = 'https://cas.jlu.edu.cn/tpass/login'
TPASS_SERVICE = 'https://jwcidentity.jlu.edu.cn/iplat-pass-jlu/thirdLogin/jlu/login'
ILEARN_SERVICE = 'https://ilearntec.jlu.edu.cn/'
ILEARN_GET_LT_URL = "https://ilearn.jlu.edu.cn/cas-server/login"
ILEARN_SSOSERVICE_URL = "https://ilearntec.jlu.edu.cn/coursecenter/main/index"
ILEARN_SSO_URL = "https://ilearn.jlu.edu.cn/iplat/ssoservice"
ILEARNTEC_GET_USER_URL = 'https://ilearntec.jlu.edu.cn/coursecenter/iplate/getUserByMid'
ILEARNTEC_TERM_LIST_URL = 'https://ilearntec.jlu.edu.cn/studycenter/platform/common/termList'
ILEARNTEC_CLASSROOM_URL = 'https://ilearntec.jlu.edu.cn/studycenter/platform/classroom/myClassroom'
ILEARNTEC_LIVE_RECORD_URL = 'https://ilearntec.jlu.edu.cn/coursecenter/liveAndRecord/getLiveAndRecordInfoList'
ILEARNRES_INFO_URL = 'https://ilearnres.jlu.edu.cn/resource-center/user/info'
ILEARNRES_LOGINRECORD_URL = 'https://ilearnres.jlu.edu.cn/resource-center/portal/loginRecord'
ILEARNRES_VIDEO_CLASS_URL = 'https://ilearnres.jlu.edu.cn/resource-center/videoclass/videoClassInfo'

# MPV Player
MPV_EXECUTABLE = 'mpv.exe' if os.name == 'nt' else 'mpv'
MPV_ARGS = ['--cache=yes', '--demuxer-max-bytes=10M', '--cache-pause=yes']

# File names and paths
VTT_FILENAME = 'temp.vtt'
CREDENTIAL_FILE = '.ilearn_cred.json'

# Default timeouts (seconds)
DEFAULT_TIMEOUT = 12
LONG_TIMEOUT = 15

# HTTP request headers
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Charset": "utf-8,iso-8859-1;q=0.7,*;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 16_1; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

# ============================================================================
# Global Session
# ============================================================================

session = requests.Session()
session.headers.update(DEFAULT_HEADERS)


# ============================================================================
# Multiprocessing Helper Functions
# ============================================================================


def _start_mpv_worker(video_path: str, vtt_filename: str, mute: bool = False) -> None:
    """
    Worker function for starting MPV player in a separate process.

    This function runs in a child process and blocks until the MPV window is closed.

    Args:
        video_path: Path to video file
        vtt_filename: Path to subtitle file
        mute: Whether to mute the audio
    """
    command = [MPV_EXECUTABLE, *MPV_ARGS, video_path, f'--sub-file={vtt_filename}']
    if mute:
        command.append('--mute=yes')

    subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


# ============================================================================
# Credential Management Functions
# ============================================================================


def save_credentials(username: str, password: str) -> None:
    """
    Save username and password to local credential file.

    Args:
        username: Username to save
        password: Password to save
    """
    try:
        with open(CREDENTIAL_FILE, 'w', encoding='utf-8') as f:
            json.dump({'username': username, 'password': password}, f)
    except Exception as e:
        print(f"保存账号信息失败: {e}")


def load_credentials() -> Tuple[Optional[str], Optional[str]]:
    """
    Load saved credentials from local file.

    Returns:
        Tuple of (username, password) or (None, None) if not found
    """
    if not os.path.exists(CREDENTIAL_FILE):
        return None, None

    try:
        with open(CREDENTIAL_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('username'), data.get('password')
    except Exception:
        return None, None


def delete_credentials() -> None:
    """Delete saved credential file."""
    if os.path.exists(CREDENTIAL_FILE):
        try:
            os.remove(CREDENTIAL_FILE)
            print("已清除保存的账号信息。")
        except Exception as e:
            print(f"清除账号信息失败: {e}")


# ============================================================================
# Utility Functions
# ============================================================================


def now_ms() -> int:
    """Get current time in milliseconds since epoch."""
    return int(time.time() * 1000)


def strip_callback_wrapper(text: str) -> str:
    """
    Extract JSON content from JSONP callback wrapper.

    Args:
        text: JSONP callback string like "callback({...})"

    Returns:
        JSON string without callback wrapper

    Raises:
        ValueError: If callback wrapper format is invalid
    """
    first = text.find('(')
    last = text.rfind(')')
    if first == -1 or last == -1 or last <= first:
        raise ValueError("Unexpected callback wrapper format")
    return text[first + 1:last]


def copy_cookies_to_domain(dest_domain: str, cookie_names: Optional[List[str]] = None) -> None:
    """
    Copy cookies from session to a specific domain.

    Args:
        dest_domain: Target domain for cookies
        cookie_names: List of cookie names to copy, defaults to all cookies
    """
    if cookie_names is None:
        cookie_names = [c.name for c in session.cookies]

    for name in cookie_names:
        val = None
        for c in session.cookies:
            if c.name == name:
                val = c.value
                break

        if val:
            try:
                newc = create_cookie(name=name, value=val, domain=dest_domain, path="/")
                session.cookies.set_cookie(newc)
            except Exception:
                pass


def attempt_sso(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = DEFAULT_TIMEOUT) -> Optional[
    requests.Response]:
    """
    Attempt SSO connection with error handling.

    Args:
        url: SSO URL to access
        headers: HTTP headers for request
        timeout: Request timeout in seconds

    Returns:
        Response object if successful, None on exception
    """
    try:
        return session.get(url, headers=headers or {}, allow_redirects=True, timeout=timeout)
    except Exception:
        return None


# ============================================================================
# Authentication Functions
# ============================================================================


def login_tpass(username: str, password: str) -> bool:
    """
    Authenticate with JLU TPASS and iLearn systems.

    This function performs a multi-step authentication flow:
    1. GET TPASS login page and extract form tokens
    2. Submit RSA-encrypted credentials to CAS
    3. Extract authentication tokens from TPASS
    4. Perform SSO handshake with iLearn
    5. Verify successful authentication

    Args:
        username: JLU email username (before @)
        password: Email password

    Returns:
        True if authentication successful, False otherwise
    """
    # Step 1: GET TPASS login page
    tpass_url = f"{CAS_URL}?service={urllib.parse.quote(TPASS_SERVICE, safe='')}"
    resp = session.get(tpass_url, timeout=LONG_TIMEOUT)
    if resp.status_code != 200:
        return False

    soup = BeautifulSoup(resp.text, 'html.parser')
    input_lt = soup.find('input', id='lt')
    input_execution = soup.find('input', attrs={'name': 'execution'})
    input_event = soup.find('input', attrs={'name': '_eventId'})

    if not input_lt or not input_execution or not input_event:
        return False

    cas_lt = input_lt.get('value', '')
    cas_execution = input_execution.get('value', '')
    cas_event = input_event.get('value', '')

    # Step 2: RSA encrypt credentials and submit
    rsa_value = des.desInit(username, password, cas_lt)
    payload = {
        'rsa': rsa_value,
        'ul': str(len(username)),
        'pl': str(len(password)),
        'sl': '0',
        'lt': cas_lt,
        'execution': cas_execution,
        '_eventId': cas_event
    }

    login_post_url = f"{CAS_URL}?service={urllib.parse.quote(TPASS_SERVICE, safe='')}"
    post_resp = session.post(login_post_url, data=payload, timeout=LONG_TIMEOUT)
    if post_resp.status_code != 200:
        return False

    # Step 3: Extract authentication credentials
    ticket_soup = BeautifulSoup(post_resp.text, 'html.parser')
    cas_username_tag = ticket_soup.find(id='username')
    cas_password_tag = ticket_soup.find(id='password')
    if not cas_username_tag or not cas_password_tag:
        return False

    cas_username = cas_username_tag.get('value', '')
    cas_password = cas_password_tag.get('value', '')
    if not cas_username or not cas_password:
        return False

    cas_password_base64 = base64.b64encode(cas_password.encode('utf-8')).decode('utf-8')

    # Step 4: iLearn SSO handshake - get LT token
    ts0 = now_ms()
    params_getlt = {
        'service': ILEARN_SERVICE,
        'get-lt': 'true',
        'callback': 'jsonpcallback',
        'n': str(ts0 + 1),
        '_': str(ts0)
    }
    getlt_resp = session.get(ILEARN_GET_LT_URL, params=params_getlt, timeout=DEFAULT_TIMEOUT)
    if getlt_resp.status_code != 200:
        return False

    try:
        inner_json_text = strip_callback_wrapper(getlt_resp.text)
        ilearn_getlt_json = json.loads(inner_json_text)
    except Exception:
        return False

    ilearn_lt = ilearn_getlt_json.get('lt')
    ilearn_execution = ilearn_getlt_json.get('execution')
    if not ilearn_lt:
        return False

    # Step 5: iLearn login with ticket exchange
    ts = now_ms()
    login_payloads = {
        'service': ILEARN_SERVICE,
        'username': cas_username,
        'password': cas_password_base64,
        'callback': 'logincallback',
        'lt': ilearn_lt,
        'execution': ilearn_execution or '',
        'n': str(ts + 1),
        'isajax': 'true',
        'isframe': 'true',
        '_eventId': 'submit',
        '_': str(ts)
    }
    login_ilearn_resp = session.get(ILEARN_GET_LT_URL, params=login_payloads, timeout=DEFAULT_TIMEOUT)
    if login_ilearn_resp.status_code != 200:
        return False

    try:
        inner_json_text2 = strip_callback_wrapper(login_ilearn_resp.text)
        ilearn_login_json = json.loads(inner_json_text2)
    except Exception:
        return False

    # Step 6: Extract ticket from response
    ticket = ilearn_login_json.get('ticket') or (ilearn_login_json.get('data') or {}).get('ticket')
    if not ticket:
        ticket = _find_ticket_recursive(ilearn_login_json)

    if not ticket:
        return False

    # Step 7: SSO simulation - navigate as browser would
    try:
        session.get("https://ilearn.jlu.edu.cn/", timeout=10)
    except Exception:
        pass

    sso_url_no_ticket = f"{ILEARN_SSO_URL}?ssoservice={ILEARN_SERVICE}"
    headers_nav = {
        "Referer": "https://ilearn.jlu.edu.cn/",
        "Origin": "https://ilearn.jlu.edu.cn",
        "User-Agent": session.headers.get("User-Agent", ""),
        "Accept": session.headers.get("Accept", ""),
        "Accept-Language": session.headers.get("Accept-Language", "")
    }
    resp_nav = session.get(sso_url_no_ticket, headers=headers_nav, allow_redirects=True, timeout=LONG_TIMEOUT)
    if resp_nav and resp_nav.status_code == 200:
        main_resp = session.get(ILEARN_SSOSERVICE_URL, timeout=DEFAULT_TIMEOUT)
        return main_resp.status_code == 200

    # Step 8: Fallback - try various ticket encoding formats
    cookie_names = [c.name for c in session.cookies]
    copy_cookies_to_domain(".ilearn.jlu.edu.cn", cookie_names)
    copy_cookies_to_domain(".ilearntec.jlu.edu.cn", cookie_names)
    time.sleep(0.12)

    sso_url_ticket_raw = f"{ILEARN_SSO_URL}?ssoservice={ILEARN_SERVICE}&ticket={ticket}"
    r_ticket = attempt_sso(sso_url_ticket_raw, headers=headers_nav)
    if r_ticket and r_ticket.status_code == 200:
        main_resp = session.get(ILEARN_SSOSERVICE_URL, timeout=DEFAULT_TIMEOUT)
        return main_resp.status_code == 200

    for t_variant in (urllib.parse.quote(ticket, safe='/'), urllib.parse.quote(ticket, safe='')):
        url_v = f"{ILEARN_SSO_URL}?ssoservice={ILEARN_SERVICE}&ticket={t_variant}"
        rv = attempt_sso(url_v, headers=headers_nav)
        if rv and rv.status_code == 200:
            main_resp = session.get(ILEARN_SSOSERVICE_URL, timeout=DEFAULT_TIMEOUT)
            return main_resp.status_code == 200

    return False


def _find_ticket_recursive(obj: Any) -> Optional[str]:
    """
    Recursively search for ticket in nested data structure.

    Args:
        obj: Object to search (dict, list, or primitive)

    Returns:
        Ticket string if found, None otherwise
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() == 'ticket' and isinstance(v, str):
                return v
            res = _find_ticket_recursive(v)
            if res:
                return res
    elif isinstance(obj, list):
        for it in obj:
            res = _find_ticket_recursive(it)
            if res:
                return res
    return None


def get_user_by_id() -> bool:
    """
    Verify user authentication by fetching user info from iLearnTec.

    Returns:
        True if user info retrieved successfully, False otherwise
    """
    ilearntec_session = session.get(ILEARNTEC_GET_USER_URL)
    return ilearntec_session.status_code == 200


# ============================================================================
# Data Model Classes
# ============================================================================


class Lesson:
    """Represents a classroom/course session."""

    def __init__(self, id: str, name: str, courseId: str, courseName: str,
                 teacherName: str, cover: str, statusName: str,
                 classroomId: str, termId: str) -> None:
        """
        Initialize Lesson object.

        Args:
            id: Lesson ID
            name: Lesson name
            courseId: Course ID
            courseName: Course name
            teacherName: Instructor name
            cover: Cover image URL
            statusName: Status name
            classroomId: Classroom ID
            termId: Term ID
        """
        self.id = id
        self.name = name
        self.courseId = courseId
        self.courseName = courseName
        self.teacherName = teacherName
        self.cover = cover
        self.statusName = statusName
        self.classroomId = classroomId
        self.termId = termId


class LessonVideosInfo:
    """Represents information about lesson video recordings."""

    def __init__(self, resourceId: str, courseName: str, liveRecordName: str,
                 buildingName: str, currentWeek: int, currentDay: int,
                 currentDate: str, roomName: str, section: int,
                 timeRange: str) -> None:
        """
        Initialize LessonVideosInfo object.

        Args:
            resourceId: Resource ID
            courseName: Course name
            liveRecordName: Recording name
            buildingName: Building name
            currentWeek: Current week number
            currentDay: Current day of week
            currentDate: Current date
            roomName: Room name
            section: Class section
            timeRange: Time range of class
        """
        self.resourceId = resourceId
        self.courseName = courseName
        self.liveRecordName = liveRecordName
        self.buildingName = buildingName
        self.currentWeek = currentWeek
        self.currentDay = currentDay
        self.currentDate = currentDate
        self.roomName = roomName
        self.section = section
        self.timeRange = timeRange


class Video:
    """Represents a video file with metadata."""

    def __init__(self, id: str, videoCode: str, videoPath: str,
                 videoName: str, videoSize: str, resourceName: str,
                 vttPath: str) -> None:
        """
        Initialize Video object.

        Args:
            id: Video ID
            videoCode: Video code
            videoPath: URL path to video file
            videoName: Display name of video
            videoSize: Size of video file
            resourceName: Resource/lesson name
            vttPath: URL path to subtitle file
        """
        self.id = id
        self.videoCode = videoCode
        self.videoPath = videoPath
        self.videoName = videoName
        self.videoSize = videoSize
        self.resourceName = resourceName
        self.vttPath = vttPath


# ============================================================================
# Course and Lesson Functions
# ============================================================================


def get_term_list_to_pylist() -> List[Dict[str, Any]]:
    """
    Fetch list of available academic terms.

    Returns:
        List of term dictionaries with keys like 'id', 'year', 'num'

    Raises:
        Exception: If term list retrieval fails
    """
    term_list_session = session.post(ILEARNTEC_TERM_LIST_URL)
    if term_list_session.status_code != 200:
        raise Exception("Failed to retrieve term list")

    tl = term_list_session.text
    tljson = json.loads(tl)
    return tljson.get('data', {}).get('dataList', [])


def get_lessons_from_termlist(termYear: str, term: str) -> List[Lesson]:
    """
    Retrieve list of lessons for a specific academic term.

    Args:
        termYear: Academic year (e.g., '2023-2024')
        term: Semester number ('1' or '2')

    Returns:
        List of Lesson objects
    """
    query_lessons_url = f'{ILEARNTEC_CLASSROOM_URL}?termYear={termYear}&term={term}'
    query_lessons_session = session.get(query_lessons_url)
    lessons_list = []

    if query_lessons_session.status_code != 200:
        return lessons_list

    lessons: str = query_lessons_session.text
    lessons_json = json.loads(lessons).get('data', {}).get('dataList', [])

    for l in lessons_json:
        thislesson = Lesson(
            id=l['id'],
            name=l['name'],
            courseId=l['courseId'],
            courseName=l['courseName'],
            teacherName=l['teacherName'],
            cover=l['cover'],
            statusName=l['statusName'],
            classroomId=l['classroomId'],
            termId=l['termId']
        )
        lessons_list.append(thislesson)

    return lessons_list


def get_year(tl: List[Dict[str, Any]]) -> set:
    """
    Extract unique academic years from term list.

    Args:
        tl: Term list from get_term_list_to_pylist()

    Returns:
        Set of year strings
    """
    years = set()
    for td in tl:
        years.add(td['year'])
    return years


def get_termId(tl: List[Dict[str, Any]], termYear: str, term: str) -> str:
    """
    Find term ID matching given year and semester.

    Args:
        tl: Term list from get_term_list_to_pylist()
        termYear: Academic year to search for
        term: Semester number to search for

    Returns:
        Term ID if found, empty string otherwise
    """
    for item in tl:
        if item['year'] == termYear and item['num'] == term:
            return item['id']
    return ''


# ============================================================================
# User Interaction Functions
# ============================================================================


def user_login_flow() -> Optional[Tuple[str, str]]:
    """
    Handle user login flow with saved credential support.

    Flow:
    1. Try to load saved credentials
    2. If found, ask user if they want to use them
    3. If not or login fails, prompt for new credentials
    4. Save credentials after successful login

    Returns:
        Tuple of (username, password) on success, None on failure
    """
    saved_user, saved_pwd = load_credentials()

    # Try saved credentials first
    if saved_user and saved_pwd:
        ans = input(f"检测到已保存账号 '{saved_user}'，是否使用此账号登录？(Y/n)：").strip().lower()
        if ans in ("", "y", "yes"):
            print("使用已保存账号登录...")
            if login_tpass(saved_user, saved_pwd):
                print("✓ 登录成功！")
                return saved_user, saved_pwd
            else:
                print("✗ 登录失败，请重新输入账号密码。")

    # Prompt for manual input
    print("\n请输入账号密码进行登录：")
    while True:
        u = input('邮箱账号（@之前的部分）：').strip()
        if not u:
            print("账号不能为空！")
            continue

        p = getpass.getpass('邮箱密码（输入不会显示）：')
        if not p:
            print("密码不能为空！")
            continue

        print("登录中...")
        if login_tpass(u, p):
            print("✓ 登录成功！")
            # Ask if user wants to save credentials
            save_ans = input("是否保存账号信息用于下次登录？(Y/n)：").strip().lower()
            if save_ans in ("", "y", "yes"):
                save_credentials(u, p)
                print("✓ 账号信息已保存。")
            return u, p
        else:
            print("✗ 账号或密码错误，请重试。\n")


def choose_term(term_list: List[Dict[str, Any]]) -> Optional[Tuple[str, str]]:
    """
    Prompt user to select academic term with back option.

    Args:
        term_list: List of available terms

    Returns:
        Tuple of (termYear, term) or None if user chooses to go back
    """
    years = sorted(get_year(term_list))

    while True:
        print(f"\n可选学年：{', '.join(years)}")
        print("输入 'b' 返回上级菜单")

        termYear: str = input("请输入你想查看的学年：").strip()
        if termYear.lower() == 'b':
            return None

        if termYear not in years:
            print("✗ 学年不存在，请重试。")
            continue

        term: str = input("请输入你想查看的学期（1/2，或 'b' 返回）：").strip()
        if term.lower() == 'b':
            continue

        if term in ('1', '2'):
            return termYear, term
        else:
            print("✗ 学期只能是 1 或 2，请重试。")


def choose_lesson(all_lessons_this_term: List[Lesson]) -> Optional[Lesson]:
    """
    Prompt user to select lesson by index with back option.

    Args:
        all_lessons_this_term: List of lessons available

    Returns:
        Selected Lesson object or None if user chooses to go back
    """
    if not all_lessons_this_term:
        print("✗ 当前学期没有课程信息。")
        return None

    while True:
        print("\n课程列表：")
        print(f"{'编号':<6} {'课程名':<30} {'任课教师':<20} {'状态':<15}")
        print("-" * 71)
        for idx, lesson in enumerate(all_lessons_this_term):
            print(f"{idx:<6} {lesson.courseName:<30} {lesson.teacherName:<20} {lesson.statusName:<15}")

        print("\n输入 'b' 返回上级菜单")
        idx_inp = input("请输入你要浏览的课程编号：").strip()

        if idx_inp.lower() == 'b':
            return None

        if not idx_inp.isdigit():
            print("✗ 请输入有效的编号。")
            continue

        idx = int(idx_inp)
        if 0 <= idx < len(all_lessons_this_term):
            return all_lessons_this_term[idx]
        else:
            print(f"✗ 编号范围应为 0~{len(all_lessons_this_term) - 1}，请重试。")


def choose_video(video_teacher_list: List[Video], video_HDMI_list: List[Video]) -> Optional[int]:
    """
    Prompt user to select video by index with back option.

    Args:
        video_teacher_list: List of teacher camera videos
        video_HDMI_list: List of classroom videos

    Returns:
        Index of selected video or None if user chooses to go back
    """
    if not video_teacher_list:
        print("✗ 没有可用的视频。")
        return None

    while True:
        print("\n视频列表：")
        print(f"{'编号':<6} {'课程信息':<30} {'视频大小':<20}")
        print("-" * 56)
        for i, (vt, vh) in enumerate(zip(video_teacher_list, video_HDMI_list)):
            print(f"{i:<6} {vt.resourceName:<30} {vt.videoSize}/{vh.videoSize}")

        print("\n输入 'b' 返回上级菜单")
        n = input("请输入你想要观看的视频编号：").strip()

        if n.lower() == 'b':
            return None

        if not n.isdigit():
            print("✗ 请输入有效的编号。")
            continue

        idx = int(n)
        if 0 <= idx < len(video_teacher_list):
            return idx
        else:
            print(f"✗ 编号范围应为 0~{len(video_teacher_list) - 1}，请重试。")


# ============================================================================
# Business Logic Functions
# ============================================================================


def fetch_live_and_record_list(termId: str, lesson_id_s: str) -> List[LessonVideosInfo]:
    """
    Fetch list of live and recorded lessons for a specific course.

    Args:
        termId: Term ID
        lesson_id_s: Lesson ID

    Returns:
        List of LessonVideosInfo objects
    """
    params = {
        'memberId': None,
        'termId': termId,
        'roomType': 0,
        'identity': 2,
        'liveStatus': 0,
        'submitStatus': 0,
        'weekNum': None,
        'dayNum': None,
        'timeRange': None,
        'teachClassId': lesson_id_s,
    }

    live_and_record_list = []
    live_and_record_info = session.get(ILEARNTEC_LIVE_RECORD_URL, params=params)

    if live_and_record_info.status_code == 200:
        live_and_record_json = json.loads(live_and_record_info.text)
        lessons_resource_info_list = live_and_record_json.get('data', {}).get('dataList', [])

        for i in lessons_resource_info_list:
            resource = LessonVideosInfo(
                resourceId=i['resourceId'],
                courseName=i['courseName'],
                liveRecordName=i['liveRecordName'],
                buildingName=i['buildingName'],
                currentWeek=i['currentWeek'],
                currentDay=i['currentDay'],
                currentDate=i['currentDate'],
                roomName=i['roomName'],
                section=i['section'],
                timeRange=i['timeRange']
            )
            live_and_record_list.append(resource)

    return live_and_record_list


def fetch_video_lists(live_and_record_list: List[LessonVideosInfo]) -> Tuple[List[Video], List[Video], int]:
    """
    Fetch video information for all lessons in the list.

    Args:
        live_and_record_list: List of lesson recording resources

    Returns:
        Tuple of (video_teacher_list, video_HDMI_list, count)
    """
    video_HDMI_list = []
    video_teacher_list = []
    cnt = 0

    # Fetch resource center info
    try:
        session.get(ILEARNRES_INFO_URL)
        session.get(ILEARNRES_LOGINRECORD_URL)
    except Exception:
        pass

    for item in live_and_record_list:
        resourceId = item.resourceId
        resource_url = f'{ILEARNRES_VIDEO_CLASS_URL}?resourceId={resourceId}'
        resource = session.get(resource_url)

        if resource.status_code != 200:
            continue

        resource_json = json.loads(resource.text)

        if resource_json.get('data') is None:
            break

        resource_name = resource_json['data']['resourceName']
        vtt_path = resource_json['data']['phaseUrl']
        video_list = resource_json['data']['videoList']

        if len(video_list) < 2:
            continue

        # Extract teacher video
        teacher_video_data = video_list[0]
        video_teacher = Video(
            id=teacher_video_data['id'],
            videoCode=teacher_video_data['videoCode'],
            videoPath=teacher_video_data['videoPath'],
            videoName=teacher_video_data['videoName'],
            videoSize=teacher_video_data['videoSize'],
            resourceName=resource_name,
            vttPath=vtt_path
        )
        video_teacher_list.append(video_teacher)

        # Extract HDMI video
        hdmi_video_data = video_list[1]
        video_hdmi = Video(
            id=hdmi_video_data['id'],
            videoCode=hdmi_video_data['videoCode'],
            videoPath=hdmi_video_data['videoPath'],
            videoName=hdmi_video_data['videoName'],
            videoSize=hdmi_video_data['videoSize'],
            resourceName=resource_name,
            vttPath=vtt_path
        )
        video_HDMI_list.append(video_hdmi)

        cnt += 1

    return video_teacher_list, video_HDMI_list, cnt


def download_vtt_file(vtt_path: str, vtt_filename: str = VTT_FILENAME) -> None:
    """
    Download subtitle file from URL and save locally.

    Args:
        vtt_path: URL to subtitle file
        vtt_filename: Local filename to save to
    """
    if os.path.exists(vtt_filename):
        os.remove(vtt_filename)

    try:
        with open(vtt_filename, 'wb') as f:
            vtt_content = requests.get(vtt_path).content
            f.write(vtt_content)
    except Exception as e:
        print(f"✗ 下载字幕失败: {e}")


# ============================================================================
# Video Playback Functions
# ============================================================================


def play_videos_simul(video_path_0_arg: str, video_path_1_arg: str,
                      vtt_filename: str = VTT_FILENAME) -> None:
    """
    Play two video streams in parallel using separate processes.

    Starts two MPV processes with a small delay between them to ensure
    they start nearly simultaneously (within ~50-100ms). Both processes
    block until the user closes the windows.

    Key differences from Pool approach:
    - Uses multiprocessing.Process directly for explicit process control
    - main process blocks on .join() until both MPV windows close
    - Two windows typically start within 50-500ms of each other
    - More intuitive synchronization: main thread waits for windows

    Args:
        video_path_0_arg: Path to teacher camera video
        video_path_1_arg: Path to classroom video
        vtt_filename: Subtitle filename
    """
    print("\n▶ 正在启动播放器...")
    start_time = time.time()

    # Create two separate processes for video playback
    p0 = Process(target=_start_mpv_worker, args=(video_path_0_arg, vtt_filename, False))
    p1 = Process(target=_start_mpv_worker, args=(video_path_1_arg, vtt_filename, True))

    # Start first process
    p0.start()

    # Small delay to stagger process startup (50-100ms is optimal)
    time.sleep(0.05)

    # Start second process
    p1.start()

    # Block main thread until both processes complete
    # (i.e., until both MPV windows are closed)
    p0.join()
    p1.join()

    elapsed = time.time() - start_time
    print(f"✓ 播放已结束（总耗时 {elapsed:.1f}s）。")


# ============================================================================
# Main Program
# ============================================================================


def main() -> int:
    """
    Main entry point for iLearn video downloader.

    Program flow with multi-level menu system:
    1. User authentication (with saved credentials support)
    2. Select academic term (with back option)
    3. Select course/lesson by index (with back option)
    4. Fetch and select video by index (with back option)
    5. Download subtitles and play videos using multiprocessing.Process
    6. After playback, return to video selection

    Returns:
        0 on successful completion, 1 on authentication failure
    """
    try:
        while True:  # Main login loop
            # Step 1: User authentication
            login_result = user_login_flow()
            if login_result is None:
                print("登录失败，程序即将退出。")
                return 1

            u, p = login_result
            get_user_by_id()
            print("\n" + "=" * 70)
            print("登录成功！进入课程选择菜单。")
            print("=" * 70)

            while True:  # Term selection loop
                # Step 2: Get and select term
                term_list = get_term_list_to_pylist()
                term_result = choose_term(term_list)
                if term_result is None:
                    # Return to login
                    print("\n是否退出登录？(Y/n)：")
                    ans = input().strip().lower()
                    if ans in ("", "y", "yes"):
                        delete_credentials()
                        break  # Back to login
                    else:
                        continue

                termYear, term = term_result
                termId = get_termId(term_list, termYear, term)

                while True:  # Lesson selection loop
                    # Step 3: Get and select lesson
                    all_lessons_this_term = get_lessons_from_termlist(termYear, term)
                    lesson_result = choose_lesson(all_lessons_this_term)
                    if lesson_result is None:
                        break  # Back to term selection

                    lesson_id_s = lesson_result.id

                    while True:  # Video selection loop
                        # Step 4: Fetch video recording information
                        live_and_record_list = fetch_live_and_record_list(termId, lesson_id_s)
                        video_teacher_list, video_HDMI_list, cnt = fetch_video_lists(live_and_record_list)

                        # Step 5: User selects video to watch
                        n = choose_video(video_teacher_list, video_HDMI_list)
                        if n is None:
                            break  # Back to lesson selection

                        vtt_path = video_teacher_list[n].vttPath

                        # Step 6: Download subtitles
                        print("\n正在下载字幕...")
                        download_vtt_file(vtt_path)

                        # Step 7: Play videos using Process for proper synchronization
                        play_videos_simul(
                            video_teacher_list[n].videoPath,
                            video_HDMI_list[n].videoPath,
                            VTT_FILENAME
                        )

                        print("\n" + "=" * 70)
                        print("播放已结束。你可以继续选择其他视频或返回上级菜单。")
                        print("=" * 70)

    except KeyboardInterrupt:
        print("\n\n程序被用户中断。")
        return 0
    except Exception as e:
        print(f"\n程序出错: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())