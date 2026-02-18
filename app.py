import io
import re
import random
import pandas as pd
import pdfplumber
import qrcode
from PIL import Image
import streamlit as st

# 페이지 설정
st.set_page_config(
    page_title="Lotto QR Generator",
    page_icon="🎱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ===== 언어 설정 (Dictionary) =====
LANG = {
    "Korean": {
        "title": "🎱 로또 QR 생성기",
        "header_info": "생성된 QR을 복권방 기계나 동행복권 앱으로 스캔하세요.",
        "file_label": "파일 업로드 (엑셀, 텍스트, PDF)",
        "draw_label": "회차 번호 (기본값: 1211)",
        "err_type": "지원하지 않는 파일 형식입니다.",
        "err_no_num": "유효한 로또 번호(1~45, 6개)를 찾을 수 없습니다.",
        "success": "총 {}게임이 로드되었습니다.",
        "err_digit": "회차 번호는 숫자만 입력해주세요.",
        "batch": "묶음 {} ({}게임)",
        "game": "게임 {}",
        "download_qr": "QR 이미지 다운로드",
        "download_csv": "📄 생성 내역 엑셀로 저장 (CSV)",
        "csv_filename": "로또_QR_생성내역_{}.csv",
        "col_round": "회차",
        "col_batch": "묶음번호",
        "col_nums": "번호",
        "col_url": "QR코드_내용(URL)"
    },
    "English": {
        "title": "🎱 Lotto QR Generator",
        "header_info": "Scan the generated QR with the lottery machine or app.",
        "file_label": "Upload File (Excel, Text, PDF)",
        "draw_label": "Draw Number (Default: 1211)",
        "err_type": "Unsupported file type",
        "err_no_num": "No valid lotto numbers found.",
        "success": "Total {} games loaded.",
        "err_digit": "Please enter draw number as digits.",
        "batch": "Batch {} ({} games)",
        "game": "Game {}",
        "download_qr": "Download QR Image",
        "download_csv": "📄 Download History (CSV)",
        "csv_filename": "lotto_history_{}.csv",
        "col_round": "Round",
        "col_batch": "Batch",
        "col_nums": "Numbers",
        "col_url": "QR_Content(URL)"
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
    # 언어 선택
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
    
    draw_number = st.text_input(txt["draw_label"], value="1211")
    
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
    
    # 데이터 저장을 위한 리스트
    history_data = []

    # QR 생성 및 표시 루프
    for idx, block in enumerate(chunk_games(games, size=5), start=1):
        payload = build_dhlottery_qr_payload(block, draw_num)
        img = generate_qr_image(payload)
        
        # 저장용 데이터 수집
        nums_str_list = [str(sorted(nums)) for nums in block]
        history_data.append({
            txt["col_round"]: draw_num,
            txt["col_batch"]: idx,
            txt["col_nums"]: " / ".join(nums_str_list),
            txt["col_url"]: payload
        })
        
        # 이미지 데이터 생성
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()
        
        st.markdown(f"**{txt['batch'].format(idx, len(block))}**")
        
        for g_idx, nums in enumerate(block, start=1):
            st.write(f"{txt['game'].format(g_idx)}: {sorted(nums)}")
        
        st.image(img_bytes, use_container_width=True)
        
        # QR 다운로드 버튼
        buf.seek(0)
        st.download_button(
            label=txt["download_qr"],
            data=buf,
            file_name=f"lotto_qr_{draw_num}_{idx}.png",
            mime="image/png",
            key=f"btn_{idx}"
        )
        
        st.divider()

    # ===== 전체 내역 CSV 저장 버튼 =====
    if history_data:
        st.subheader("💾 저장 (Save)")
        df = pd.DataFrame(history_data)
        
        # 한글 엑셀 깨짐 방지를 위해 utf-8-sig 인코딩 사용
        csv_buffer = df.to_csv(index=False).encode('utf-8-sig')
        
        st.download_button(
            label=txt["download_csv"],
            data=csv_buffer,
            file_name=txt["csv_filename"].format(draw_num),
            mime="text/csv"
        )

if __name__ == "__main__":
    main()
