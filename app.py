import io, re, zipfile, qrcode, pandas as pd, pdfplumber, streamlit as st
from datetime import datetime
from PIL import Image

# 설정 및 스타일
st.set_page_config(page_title="Lotto QR Generator", page_icon="🎱", layout="centered")
st.markdown("<style>h1{text-align:center;} .stButton>button{width:100%;}</style>", unsafe_allow_html=True)

def get_purchasable_lotto_round():
    first_draw = datetime(2002, 12, 7)
    now = datetime.now()
    weeks = (now - first_draw).days // 7
    base = 1 + weeks + 1
    if now.weekday() == 5 and (now.hour > 20 or (now.hour == 20 and now.minute >= 20)):
        return base + 1
    return base

def parse_numbers(line):
    nums = re.findall(r'\d+', line)
    nums = [int(n) for n in nums if 1 <= int(n) <= 45]
    return sorted(list(set(nums)))[:6] if len(set(nums)) >= 6 else None

def build_dhlottery_payload(games, draw_num):
    games_str = [f"M:{''.join(str(n).zfill(2) for n in sorted(g))}" for g in games]
    return f"MSG_ESLIP{{{draw_num}}}{{({len(games)},{','.join(games_str)})}}"

def generate_qr(data):
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

def main():
    st.title("🎱 로또 QR 생성기")
    st.info("동행복권 앱/판매점 스캐너 호환 모바일 슬립지 생성")
    
    draw_num = st.text_input("회차 번호", value=str(get_purchasable_lotto_round()))
    file = st.file_uploader("파일 업로드 (Excel, TXT, PDF)", type=["xlsx", "xls", "txt", "pdf"])
    
    if file and draw_num.isdigit():
        games = []
        if "xls" in file.name:
            df = pd.read_excel(file, header=None)
            for _, row in df.iterrows():
                n = parse_numbers(" ".join(map(str, row.values)))
                if n: games.append(n)
        elif "txt" in file.name:
            lines = file.read().decode("utf-8").splitlines()
            for l in lines:
                n = parse_numbers(l)
                if n: games.append(n)
        elif "pdf" in file.name:
            with pdfplumber.open(file) as pdf:
                for pg in pdf.pages:
                    for l in (pg.extract_text() or "").splitlines():
                        n = parse_numbers(l)
                        if n: games.append(n)

        if games:
            st.success(f"총 {len(games)} 게임 로드 완료")
            for i in range(0, len(games), 5):
                block = games[i:i+5]
                payload = build_dhlottery_payload(block, draw_num)
                img = generate_qr(payload)
                
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                st.image(buf.getvalue(), caption=f"묶음 {i//5 + 1}")
                st.download_button("QR 다운로드", buf.getvalue(), f"lotto_{draw_num}_{i//5+1}.png", "image/png")
        else:
            st.error("유효한 번호를 찾을 수 없습니다.")

if __name__ == "__main__":
    main()
