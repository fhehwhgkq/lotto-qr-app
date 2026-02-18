import io
import re
import random
import zipfile
import pandas as pd
import pdfplumber
import qrcode
from PIL import Image
import streamlit as st
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Lotto QR Generator",
    page_icon="🎱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    h1 {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        font-size: 1.8rem !important;
        text-align: center !important;
    }
    @media (max-width: 400px) {
        h1 { font-size: 1.4rem !important; }
    }
    .stButton > button {
        width: 100%;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# ===== 로또 회차 자동 계산 함수 (정확한 보정) =====
def get_purchasable_lotto_round():
    """
    현재 날짜/시간 기준으로 구매 가능한 로또 회차 계산
    1 회: 2002 년 12 월 7 일 (토요일) 기준
    판매 마감: 토요일 20:20
    """
    first_draw = datetime(2002, 12, 7)  # 1 회 추첨일
    now = datetime.now()
    
    # 경과 일수 계산
    days_diff = (now - first_draw).days
    weeks_passed = days_diff // 7
    
    # 회차 계산 (보정: +1 추가)
    base_round = 1 + weeks_passed + 1
    
    # 요일 확인 (월=0, ..., 토=5)
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    
    # 토요일 20:20 지났는지 확인
    is_after_cutoff = (weekday == 5 and (hour > 20 or (hour == 20 and minute >= 20)))
    
    if is_after_cutoff:
        purchasable_round = base_round + 1
    else:
        purchasable_round = base_round
    
    return purchasable_round

# ===== 회차 계산 실행 =====
current_round = get_purchasable_lotto_round()

# ===== 언어 설정 =====
LANG = {
    "Korean": {
        "title": "🎱 로또 QR 생성기",
        "header_info": "생성된 QR 을 복권방 기계나 동행복권 앱으로 스캔하세요.",
        "file_label": "파일 업로드 (엑셀, 텍스트, PDF)",
        "draw_label": f"회차 번호 ({current_round}회 구입가능)",
        "default_round": str(current_round),
        "err_type": "지원하지 않는 파일 형식입니다.",
        "err_no_num": "유효한 로또 번호 (1~45, 6 개) 를 찾을 수 없습니다.",
        "success": "총 {} 게임이 로드되었습니다.",
        "err_digit": "회차 번호는 숫자만 입력해주세요.",
        "zip_btn": "📦 전체 QR 이미지 한번에 다운로드 (ZIP)",
        "zip_filename": "로또 QR_{}_전체.zip",
        "batch": "묶음 {} ({} 게임)",
        "game": "게임 {}",
        "download_qr": "이 QR 만 다운로드",
    },
    "English": {
        "title": "🎱 Lotto QR Generator",
        "header_info": "Scan the generated QR with the lottery machine or app.",
        "file_label": "Upload File (Excel, Text, PDF)",
        "draw_label": f"Draw Number ({current_round} purchasable)",
        "default_round": str(current_round),
        "err_type": "Unsupported file type",
        "err_no_num": "No valid lotto numbers found.",
        "success": "Total {} games loaded.",
        "err_digit": "Please enter draw number as digits.",
        "zip_btn": "📦 Download All QR Images (ZIP)",
        "zip_filename": "LottoQR_{}_All.zip",
        "batch": "Batch {} ({} games)",
        "game": "Game {}",
        "download_qr": "Download This QR",
    }
}

# ===== 유틸리티 함수들 =====
def parse_numbers_from_line(line):
    nums = re.findall(r'\d+', line)
    nums = [int(n) for n in nums if 1 <= int(n) <= 45]
    if len(nums) >= 6:
        return nums[:6]
    return None

def parse_excel(file):
    df = pd.read_excel(file, header=None)
    games = []
    for _, row in df.iterrows():
        nums = [n for n in row.tolist() if pd.notnull(n)]
        if len(nums) >= 6:
            nums = [int(n) for n in nums[:6]]
            if all(1 <= n <= 45 for n in nums):
                games.append(nums)
    return games

def parse_text(file):
    content = file.read().decode("utf-8", errors="ignore")
    lines = content.splitlines()
    games = []
    for line in lines:
        nums = parse_numbers_from_line(line)
        if nums:
            games.append(nums)
    return games

def parse_pdf(file):
    games = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.splitlines()
            for line in lines:
                nums = parse_numbers_from_line(line)
                if nums:
                    games.append(nums)
    return games

def chunk_games(games, size=5):
    for i in range(0, len(games), size):
        yield games[i:i+size]

def build_dhlottery_qr_payload(games_block, draw_number):
    draw_str = str(draw_number).zfill(4)
    url = f"http://qr.dhlottery.co.kr/?v={draw_str}"
    for nums in games_block:
        nums_sorted = sorted(nums)
        game_str = "".join(str(n).zfill(2) for n in nums_sorted)
        url += f"m{game_str}"
    random_suffix = "".join([str(random.randint(0, 9)) for _ in range(18)])
    url += random_suffix
    return url

def generate_qr_image(data, box_size=8, border=2):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img

# ===== 메인 앱 =====
def main():
    lang_choice = st.radio(
        "Language / 언어",
        ("Korean", "English"),
        horizontal=True
    )
    txt = LANG[lang_choice]

    st.title(txt["title"])
    st.info(txt["header_info"])
    
    uploaded_file = st.file_uploader(
        txt["file_label"],
        type=["xlsx", "xls", "txt", "pdf"]
    )
    
    # 자동 계산된 회차번호가 기본값으로 표시
    draw_number = st.text_input(
        txt["draw_label"], 
        value=txt["default_round"]
    )
    
    if not uploaded_file:
        return
    
    suffix = uploaded_file.name.split(".")[-1].lower()
    
    try:
        if suffix in ["xlsx", "xls"]:
            games = parse_excel(uploaded_file)
        elif suffix == "txt":
            games = parse_text(uploaded_file)
        elif suffix == "pdf":
            file_bytes = uploaded_file.read()
            games = parse_pdf(io.BytesIO(file_bytes))
        else:
            st.error(txt["err_type"])
            return
    except Exception as e:
        st.error(f"Error: {e}")
        return
    
    if not games:
        st.error(txt["err_no_num"])
        return
    
    st.success(txt["success"].format(len(games)))
    
    try:
        draw_num = int(draw_number)
    except:
        st.error(txt["err_digit"])
        return
    
    qr_data_list = []
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for idx, block in enumerate(chunk_games(games, size=5), start=1):
            payload = build_dhlottery_qr_payload(block, draw_num)
            img = generate_qr_image(payload)
            
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format="PNG")
            img_bytes = img_byte_arr.getvalue()
            
            filename = f"Lotto_{draw_num}_{idx}.png"
            zf.writestr(filename, img_bytes)
            
            qr_data_list.append({
                "idx": idx,
                "block": block,
                "img_bytes": img_bytes,
                "filename": filename
            })

    zip_buffer.seek(0)
    
    st.download_button(
        label=txt["zip_btn"],
        data=zip_buffer,
        file_name=txt["zip_filename"].format(draw_num),
        mime="application/zip",
        type="primary"
    )
    
    st.divider()

    for item in qr_data_list:
        idx = item["idx"]
        block = item["block"]
        img_bytes = item["img_bytes"]
        filename = item["filename"]
        
        st.markdown(f"**{txt['batch'].format(idx, len(block))}**")
        
        for g_idx, nums in enumerate(block, start=1):
            st.write(f"{txt['game'].format(g_idx)}: {sorted(nums)}")
        
        st.image(img_bytes, use_container_width=True)
        
        st.download_button(
            label=txt["download_qr"],
            data=img_bytes,
            file_name=filename,
            mime="image/png",
            key=f"btn_{idx}"
        )
        st.markdown("---")

if __name__ == "__main__":
    main()
