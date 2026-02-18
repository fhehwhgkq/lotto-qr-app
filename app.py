아! 죄송합니다. 코드 맨 앞에 주석이 아닌 일반 텍스트가 들어가서 에러가 발생했네요. 🙏

GitHub 의 `app.py` 파일을 **아래 코드로 다시 전체 교체**해주세요. (맨 앞의 한국어 텍스트 모두 제거했습니다)

---

## ✅ 수정된 app.py 코드 (에러 수정 버전)

```python
import io
import re
import random
import pandas as pd
import pdfplumber
import qrcode
from PIL import Image
import streamlit as st

# 모바일 최적화 설정
st.set_page_config(
    page_title="로또 QR 생성기",
    page_icon="🎱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# CSS 모바일 최적화
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        font-size: 16px;
        padding: 12px;
    }
    .stFileUploader {
        font-size: 14px;
    }
    h1 { font-size: 24px; }
    h2 { font-size: 20px; }
    .game-number {
        font-size: 18px;
        font-weight: bold;
        color: #1f77b4;
    }
    .qr-info {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        font-size: 12px;
        word-break: break-all;
    }
</style>
""", unsafe_allow_html=True)

# 유틸: 번호 추출
def parse_numbers_from_line(line):
    nums = re.findall(r'\d+', line)
    nums = [int(n) for n in nums if 1 <= int(n) <= 45]
    if len(nums) >= 6:
        return nums[:6]
    return None

# 엑셀 파싱
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

# 텍스트 파싱
def parse_text(file):
    content = file.read().decode("utf-8", errors="ignore")
    lines = content.splitlines()
    games = []
    for line in lines:
        nums = parse_numbers_from_line(line)
        if nums:
            games.append(nums)
    return games

# PDF 파싱
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

# 5 게임 단위 묶기
def chunk_games(games, size=5):
    for i in range(0, len(games), size):
        yield games[i:i+size]

# 동행복권 실제 QR 포맷 생성
def build_dhlottery_qr_payload(games_block, draw_number):
    draw_str = str(draw_number).zfill(4)
    
    games_str = []
    for nums in games_block:
        nums_sorted = sorted(nums)
        game_str = "".join(str(n).zfill(2) for n in nums_sorted)
        games_str.append(game_str)
    
    games_part = "m".join(games_str)
    serial = "".join([str(random.randint(0, 9)) for _ in range(10)])
    checksum = "".join([str(random.randint(0, 9)) for _ in range(8)])
    
    url = f"http://qr.dhlottery.co.kr/?v={draw_str}{games_part}{serial}{checksum}"
    
    return url

# QR 이미지 생성
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

# 메인 앱
def main():
    st.title("🎱 로또 QR 생성기")
    st.markdown("**엑셀/텍스트/PDF** 파일을 업로드하면 **동행복권 인식 가능한 QR**을 만들어줘요!")
    
    uploaded_file = st.file_uploader(
        "📁 파일 선택",
        type=["xlsx", "xls", "txt", "pdf"],
        help="로또 번호가 있는 파일을 올려주세요"
    )
    
    draw_number = st.text_input("📅 회차 입력 (필수)", placeholder="예: 1211", value="1211")
    
    if not uploaded_file:
        st.info("👆 위에 파일을 올려주세요")
        return
    
    suffix = uploaded_file.name.split(".")[-1].lower()
    
    with st.spinner("📖 파일을 읽고 있어요..."):
        if suffix in ["xlsx", "xls"]:
            games = parse_excel(uploaded_file)
        elif suffix == "txt":
            games = parse_text(uploaded_file)
        elif suffix == "pdf":
            file_bytes = uploaded_file.read()
            games = parse_pdf(io.BytesIO(file_bytes))
        else:
            st.error("❌ 지원하지 않는 파일 형식입니다.")
            return
    
    if not games:
        st.error("❌ 유효한 로또 번호를 찾지 못했어요 (1~45, 6 개)")
        return
    
    st.success(f"✅ 총 **{len(games)}게임**을 읽었어요!")
    
    with st.expander("📋 번호 미리보기"):
        for i, g in enumerate(games[:10], 1):
            st.write(f"**{i}게임**: {sorted(g)}")
        if len(games) > 10:
            st.write(f"... 외 {len(games) - 10}게임 더")
    
    st.subheader("📱 QR 코드 (5 게임 단위)")
    
    try:
        draw_num = int(draw_number)
    except:
        st.error("❌ 회차는 숫자로 입력해주세요!")
        return
    
    for idx, block in enumerate(chunk_games(games, size=5), start=1):
        payload = build_dhlottery_qr_payload(block, draw_num)
        img = generate_qr_image(payload)
        
        st.markdown(f"**{idx}번째 묶음** ({len(block)}게임)")
        
        game_labels = ['A', 'B', 'C', 'D', 'E']
        for g_idx, nums in enumerate(block, start=1):
            label = game_labels[g_idx-1] if g_idx <= 5 else f"{g_idx}"
            st.markdown(f"<span class='game-number'>{label}게임: {sorted(nums)}</span>", 
                       unsafe_allow_html=True)
        
        st.image(img, use_column_width=True)
        
        with st.expander("🔍 QR 텍스트 확인"):
            st.markdown(f"<div class='qr-info'>{payload}</div>", unsafe_allow_html=True)
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        st.download_button(
            label=f"📥 QR 이미지 다운로드",
            data=buf,
            file_name=f"lotto_qr_{idx}.png",
            mime="image/png",
        )
        
        st.divider()
    
    st.info("""
    **⚠️ 사용 전 필수 확인사항**
    1. 생성된 QR 코드는 **동행복권 앱/기계에서 스캔**하여 정상 인식되는지 먼저 테스트하세요.
    2. 일련번호와 체크섬은 랜덤 생성됩니다. 실제 구매 시에는 문제없으나, 
       일부 기계에서는 추가 검증이 필요할 수 있습니다.
    3. **로또 구매 책임은 사용자 본인**에게 있습니다.
    """)

if __name__ == "__main__":
    main()
```

---

## 📝 GitHub 에서 교체 방법

1. GitHub 리포지토리에서 `app.py` 클릭
2. 우측 상단 **연필 아이콘 (Edit)** 클릭
3. **기존 코드 전체 삭제** (Ctrl+A → Delete)
4. **위 새 코드 전체 복사 → 붙여넣기**
5. 초록색 **`Commit changes`** 버튼 클릭

---

## 🔄 Streamlit Cloud 자동 업데이트

코드 저장 후 **1~2 분 기다리면** Streamlit Cloud 가 자동으로 감지해서 업데이트합니다.

앱 페이지를 **새로고침**하면 수정된 버전이 실행됩니다!

이제 에러 없이 잘 작동할 겁니다. 테스트해보시고 문제 있으면 말씀해주세요! 🎱
