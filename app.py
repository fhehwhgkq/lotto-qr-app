import io
import re
import random
import zipfile
import pandas as pd
import pdfplumber
import qrcode
from PIL import Image
import streamlit as st
from datetime import datetime

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

# ===== 로또 회차 자동 계산 =====
def get_purchasable_lotto_round():
    first_draw = datetime(2002, 12, 7)
    now = datetime.now()
    days_diff = (now - first_draw).days
    weeks_passed = days_diff // 7
    base_round = 1 + weeks_passed + 1
    
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    
    is_after_cutoff = (weekday == 5 and (hour > 20 or (hour == 20 and minute >= 20)))
    
    if is_after_cutoff:
        purchasable_round = base_round + 1
    else:
        purchasable_round = base_round
    
    return purchasable_round

current_round = get_purchasable_lotto_round()

# ===== 언어 설정 =====
LANG = {
    "Korean": {
        "title": "🎱 로또 QR 생성기",
        "header_info": "동행복권 앱 슬립지 호환 QR 코드",
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
        "header_info": "Donghaeng Lotto App Slip Compatible QR",
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

# ===== 동행복권 앱 슬립지 QR 포맷 =====
def build_dhlottery_eslip_payload(games_block, draw_number):
    games_str = []
    for nums in games_block:
        nums_sorted = sorted(nums)
        game_str = "".join(str(n).zfill(2) for n in nums_sorted)
        games_str.append(f"M:{game_str}")
    
    games_part = ",".join(games_str)
    payload = f"MSG_ESLIP{{{draw_number}}}{{({len(games_block)},{games_part})}}}{{}}10|"
    
    return payload

# ===== QR 이미지 생성 (사이즈 조정) =====
def generate_qr_image(data, box_size=6, border=1):
    qr = qrcode.QRCode(
        version=5,  # 버전 고정 (조밀하게)
        error_correction=qrcode.constants.ERROR_CORRECT_L,  # 에러 수정 레벨 낮춤 (더 조밀)
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
            payload = build_dhlottery_eslip_payload(block, draw_num)
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
                "filename": filename,
                "payload": payload
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
        payload = item["payload"]
        
        st.markdown(f"**{txt['batch'].format(idx, len(block))}**")
        
        for g_idx, nums in enumerate(block, start=1):
            st.write(f"{txt['game'].format(g_idx)}: {sorted(nums)}")
        
        st.image(img_bytes, use_container_width=True)
        
        with st.expander("🔍 QR 내용 확인"):
            st.code(payload, language="text")
        
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
