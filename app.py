import io, re, qrcode, pandas as pd, pdfplumber, streamlit as st
from datetime import datetime
from PIL import Image
import cv2
import numpy as np

# 스트림릿 페이지 설정
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
    uniq = sorted(list(set(nums)))
    return uniq[:6] if len(uniq) >= 6 else None

def build_dhlottery_payload(games, draw_num):
    games_str = [f"M:{''.join(str(n).zfill(2) for n in sorted(g))}" for g in games]
    return f"MSG_ESLIP{{{draw_num}}}{{({len(games)},{','.join(games_str)})}}"

def generate_qr_from_text(data, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4):
    qr = qrcode.QRCode(version=None, error_correction=error_correction, box_size=box_size, border=border)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

def decode_qr_image_with_cv2(pil_img):
    # PIL -> OpenCV(BGR) 변환
    try:
        arr = np.array(pil_img.convert('RGB'))
    except Exception:
        return None
    # RGB -> BGR
    img = arr[:, :, ::-1].copy()
    detector = cv2.QRCodeDetector()
    data, pts, straight_qrcode = detector.detectAndDecode(img)
    if data:
        return data
    return None

def load_numbers_from_file(file):
    games = []
    fname = file.name.lower()
    if fname.endswith(("xlsx","xls")):
        df = pd.read_excel(file, header=None)
        for _, row in df.iterrows():
            line = " ".join(map(str, row.values))
            n = parse_numbers(line)
            if n: games.append(n)
    elif fname.endswith("txt"):
        try:
            lines = file.read().decode("utf-8").splitlines()
        except Exception:
            # 다른 인코딩 가능성 대비
            lines = file.read().decode("cp949", errors="ignore").splitlines()
        for l in lines:
            n = parse_numbers(l)
            if n: games.append(n)
    elif fname.endswith("pdf"):
        with pdfplumber.open(file) as pdf:
            for pg in pdf.pages:
                text = pg.extract_text() or ""
                for l in text.splitlines():
                    n = parse_numbers(l)
                    if n: games.append(n)
    return games

def main():
    st.title("🎱 로또 QR 생성기 & 디코더")
    st.info("동행복권 앱/판매점 스캐너 호환 모바일 슬립지 생성 및 앱 QR 디코딩")

    # 1) 앱 QR 디코더 섹션
    st.subheader("1) 앱에서 만든 QR을 업로드하여 내부 문자열 확인")
    app_qr_file = st.file_uploader("앱 QR 이미지 업로드 (png/jpg/jpeg)", type=["png","jpg","jpeg"], key="app_qr")
    decoded_payload = None
    if app_qr_file:
        try:
            img = Image.open(app_qr_file).convert("RGB")
            st.image(img, caption="업로드한 앱 QR")
            qr_text = decode_qr_image_with_cv2(img)
            if qr_text:
                decoded_payload = qr_text
                st.success("디코딩 성공. 아래 문자열을 확인하세요.")
                st.code(qr_text)
                st.write("이 문자열을 그대로 사용하면 앱에서 생성한 것과 동일한 QR을 만들 수 있습니다.")
            else:
                st.error("QR을 읽지 못했습니다. 해상도, 화이트 마진(여백)을 확인해 주세요.")
        except Exception as e:
            st.error(f"이미지 처리 중 오류: {e}")

    # 2) 번호 파일 업로드 및 QR 생성 섹션
    st.subheader("2) 번호 파일 업로드 및 QR 생성 (Excel, TXT, PDF)")
    draw_num = st.text_input("회차 번호", value=str(get_purchasable_lotto_round()))
    num_file = st.file_uploader("번호 파일 업로드 (Excel, TXT, PDF)", type=["xlsx","xls","txt","pdf"], key="numbers")

    st.info("앱에서 디코딩한 payload가 있다면 아래 박스에 붙여넣으면 해당 payload 그대로 QR을 생성합니다.")
    override_payload_example = st.text_area("앱에서 확인한 전체 payload 붙여넣기 (선택)", height=80)

    if num_file and draw_num.isdigit():
        games = load_numbers_from_file(num_file)
        if not games:
            st.error("유효한 번호(6개)가 포함된 행을 찾지 못했습니다.")
        else:
            st.success(f"총 {len(games)} 게임 로드 완료")
            for i in range(0, len(games), 5):
                block = games[i:i+5]
                if override_payload_example.strip():
                    payload = override_payload_example.strip()
                elif decoded_payload:
                    st.write(f"앱에서 디코딩한 payload가 있습니다. 묶음 {i//5+1}에 동일 payload 사용 여부를 선택하세요.")
                    use_decoded = st.checkbox(f"묶음 {i//5+1}에 디코딩된 payload 사용", key=f"use_decoded_{i}")
                    if use_decoded:
                        payload = decoded_payload
                    else:
                        payload = build_dhlottery_payload(block, draw_num)
                else:
                    payload = build_dhlottery_payload(block, draw_num)

                img = generate_qr_from_text(payload)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                st.image(buf.getvalue(), caption=f"묶음 {i//5 + 1}")
                st.download_button("QR 다운로드", buf.getvalue(), f"lotto_{draw_num}_{i//5+1}.png", "image/png")

    # 3) 수동 QR 생성
    st.subheader("3) payload 직접 입력 및 QR 생성")
    manual_payload = st.text_area("직접 생성할 payload 입력 (예: MSG_ESLIP{...})", height=120)
    if st.button("직접 생성하고 QR 보기"):
        if manual_payload.strip():
            try:
                img = generate_qr_from_text(manual_payload.strip())
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                st.image(buf.getvalue(), caption="수동으로 생성한 QR")
                st.download_button("QR 다운로드", buf.getvalue(), "manual_qr.png", "image/png")
            except Exception as e:
                st.error(f"QR 생성 중 오류: {e}")
        else:
            st.error("payload를 입력하세요.")

if __name__ == "__main__":
    main()
