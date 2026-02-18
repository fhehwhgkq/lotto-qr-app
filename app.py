import io
import re
import random
import pandas as pd
import pdfplumber
import qrcode
from PIL import Image
import streamlit as st

st.set_page_config(
    page_title="Lotto QR",
    page_icon="🎱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

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

def main():
    st.title("Lotto QR Generator")
    
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["xlsx", "xls", "txt", "pdf"]
    )
    
    draw_number = st.text_input("Draw Number", value="1211")
    
    if not uploaded_file:
        return
    
    suffix = uploaded_file.name.split(".")[-1].lower()
    
    if suffix in ["xlsx", "xls"]:
        games = parse_excel(uploaded_file)
    elif suffix == "txt":
        games = parse_text(uploaded_file)
    elif suffix == "pdf":
        file_bytes = uploaded_file.read()
        games = parse_pdf(io.BytesIO(file_bytes))
    else:
        st.error("Unsupported file type")
        return
    
    if not games:
        st.error("No valid lotto numbers found")
        return
    
    st.success(f"Total {len(games)} games loaded")
    
    try:
        draw_num = int(draw_number)
    except:
        st.error("Please enter draw number as digits")
        return
    
    for idx, block in enumerate(chunk_games(games, size=5), start=1):
        payload = build_dhlottery_qr_payload(block, draw_num)
        img = generate_qr_image(payload)
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes = img_bytes.getvalue()
        
        st.markdown(f"**Batch {idx}** ({len(block)} games)")
        
        for g_idx, nums in enumerate(block, start=1):
            st.write(f"Game {g_idx}: {sorted(nums)}")
        
        st.image(img_bytes, use_container_width=True)
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        st.download_button(
            label="Download QR",
            data=buf.getvalue(),
            file_name=f"lotto_qr_{idx}.png",
            mime="image/png",
        )
        
        st.divider()

if __name__ == "__main__":
    main()
