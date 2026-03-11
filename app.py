import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import ast

# 페이지 설정
st.set_page_config(page_title="Nemostore Premium Dashboard v2", layout="wide")

# 한글 컬럼명 매핑 딕셔너리
COL_MAP = {
    'title': '매물명',
    'businessMiddleCodeName': '업종',
    'deposit': '보증금(만원)',
    'monthlyRent': '월세(만원)',
    'premium': '권리금(만원)',
    'size': '전용면적(㎡)',
    'floor': '층수',
    'nearSubwayStation': '인근역',
    'maintenanceFee': '관리비(만원)',
    'confirmedDateUtc': '확인일자',
    'articleType': '유형',
    'priceTypeName': '거래형태'
}

# 데이터 로드 함수
@st.cache_data
def load_data():
    # 배포를 위해 상대 경로 사용 (app.py와 같은 위치의 nemostore.db 참조)
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, 'nemostore.db')
    
    conn = sqlite3.connect(db_path)
    query_tables = "SELECT name FROM sqlite_master WHERE type='table';"
    tables = pd.read_sql(query_tables, conn)
    if not tables.empty:
        table_name = tables.iloc[0]['name']
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
        conn.close()
        
        # 전처리
        df['deposit'] = df['deposit'].fillna(0).astype(int)
        df['monthlyRent'] = df['monthlyRent'].fillna(0).astype(int)
        df['premium'] = df['premium'].fillna(0).astype(int)
        df['size'] = df['size'].fillna(0).round(1)
        
        # 이미지 URL 파싱 (문자열 리스트 형태 처리)
        def parse_urls(url_str):
            try:
                # ast.literal_eval로 안전하게 리스트 변환
                urls = ast.literal_eval(url_str)
                return urls if isinstance(urls, list) else []
            except:
                return []
        
        df['photo_list'] = df['smallPhotoUrls'].apply(parse_urls)
        df['main_photo'] = df['photo_list'].apply(lambda x: x[0] if x else "")
        
        return df
    conn.close()
    return pd.DataFrame()

df_raw = load_data()

# 세션 상태 초기화
if 'selected_article' not in st.session_state:
    st.session_state.selected_article = None

def select_article(article_id):
    st.session_state.selected_article = article_id

def clear_selection():
    st.session_state.selected_article = None

# --- 대시보드 메인 로직 ---

if st.session_state.selected_article is None:
    # 1. 목록 페이지
    st.title("🏙️ Nemostore 상가 분석 대시보드 v2")
    
    # 사이드바 필터
    st.sidebar.header("🔍 검색 필터")
    search_query = st.sidebar.text_input("매물명 또는 키워드", "")
    all_biz_types = ["전체"] + sorted(df_raw['businessMiddleCodeName'].unique().tolist())
    selected_biz = st.sidebar.selectbox("업종 선택", all_biz_types)
    
    st.sidebar.subheader("💰 가격 조건 (만원)")
    deposit_range = st.sidebar.slider("보증금", 0, int(df_raw['deposit'].max()), (0, int(df_raw['deposit'].max())), step=1000)
    rent_range = st.sidebar.slider("월세", 0, int(df_raw['monthlyRent'].max()), (0, int(df_raw['monthlyRent'].max())), step=50)
    premium_range = st.sidebar.slider("권리금", 0, int(df_raw['premium'].max()), (0, int(df_raw['premium'].max())), step=500)

    # 필터링
    filtered_df = df_raw[
        (df_raw['deposit'] >= deposit_range[0]) & (df_raw['deposit'] <= deposit_range[1]) &
        (df_raw['monthlyRent'] >= rent_range[0]) & (df_raw['monthlyRent'] <= rent_range[1]) &
        (df_raw['premium'] >= premium_range[0]) & (df_raw['premium'] <= premium_range[1])
    ]
    if search_query:
        filtered_df = filtered_df[filtered_df['title'].str.contains(search_query, case=False, na=False)]
    if selected_biz != "전체":
        filtered_df = filtered_df[filtered_df['businessMiddleCodeName'] == selected_biz]

    # KPI 지표
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("검색결과", f"{len(filtered_df)}건")
    kpi2.metric("평균 월세", f"{filtered_df['monthlyRent'].mean():,.0f}만원")
    kpi3.metric("평균 보증금", f"{filtered_df['deposit'].mean():,.0f}만원")
    kpi4.metric("평균 권리금", f"{filtered_df['premium'].mean():,.0f}만원")

    st.divider()

    # 시각화 (Plotly)
    st.subheader("📊 지역 및 업종 통계")
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        # 업종별 빈도 (Plotly)
        biz_counts = filtered_df['businessMiddleCodeName'].value_counts().head(10).reset_index()
        biz_counts.columns = ['업종', '매물수']
        fig_biz = px.bar(biz_counts, x='업종', y='매물수', title="상위 10개 업종 분포", color='매물수', color_continuous_scale='Viridis')
        st.plotly_chart(fig_biz, use_container_width=True)

    with col_chart2:
        # 면적 vs 월세 산점도 (Plotly)
        fig_scatter = px.scatter(filtered_df, x='size', y='monthlyRent', color='businessMiddleCodeName', 
                                 hover_name='title', title="전용면적 대비 월세 상관관계",
                                 labels={'size': '전용면적(㎡)', 'monthlyRent': '월세(만원)', 'businessMiddleCodeName': '업종'})
        st.plotly_chart(fig_scatter, use_container_width=True)

    # 층별 임대료 분석 (Plotly Boxplot)
    st.subheader("⬇️ 층별 임대료 변동 분석")
    fig_floor = px.box(filtered_df, x='floor', y='monthlyRent', points="all", title="층수별 월세 분포 및 이상치",
                       labels={'floor': '층수', 'monthlyRent': '월세(만원)'}, color='floor')
    st.plotly_chart(fig_floor, use_container_width=True)

    st.divider()

    # 이미지 갤러리 리스트
    st.subheader("📸 매물 갤러리")
    
    if filtered_df.empty:
        st.info("조건에 맞는 매물이 없습니다.")
    else:
        # 3열 그리드
        cols = st.columns(3)
        for idx, row in filtered_df.reset_index().iterrows():
            col = cols[idx % 3]
            with col:
                with st.container(border=True):
                    if row['main_photo']:
                        st.image(row['main_photo'], use_container_width=True)
                    else:
                        st.image("https://via.placeholder.com/300x200?text=No+Image", use_container_width=True)
                    
                    st.write(f"**{row['title'][:25]}...**")
                    st.write(f"📍 {row['nearSubwayStation'] if row['nearSubwayStation'] else '위치 정보 없음'}")
                    st.write(f"💰 {row['monthlyRent']} / {row['deposit']} (월세/보증금)")
                    
                    if st.button("상세 정보 보기", key=f"btn_{row['id']}"):
                        select_article(row['id'])

    # 데이터 테이블 (한글 컬럼명 적용)
    st.subheader("📝 매물 상세 데이터")
    table_df = filtered_df[['title', 'businessMiddleCodeName', 'deposit', 'monthlyRent', 'premium', 'size', 'floor', 'nearSubwayStation']]
    table_df.columns = [COL_MAP[c] for c in table_df.columns]
    st.dataframe(table_df, use_container_width=True)

else:
    # 2. 상세 페이지
    article = df_raw[df_raw['id'] == st.session_state.selected_article].iloc[0]
    
    st.button("⬅️ 목록으로 돌아가기", on_click=clear_selection)
    
    st.title(f"🏠 {article['title']}")
    
    col_img, col_info = st.columns([1, 1])
    
    with col_img:
        if article['photo_list']:
            selected_img = st.selectbox("매물 이미지 선택", article['photo_list'])
            st.image(selected_img, use_container_width=True)
        else:
            st.image("https://via.placeholder.com/600x400?text=No+Image", use_container_width=True)

    with col_info:
        st.subheader("📌 매물 상세 정보")
        info_data = {
            "항목": [],
            "내용": []
        }
        for eng, kor in COL_MAP.items():
            if eng in article:
                val = article[eng]
                if eng in ['deposit', 'monthlyRent', 'premium']:
                    val = f"{val:,} 만원"
                elif eng == 'size':
                    val = f"{val} ㎡"
                info_data["항목"].append(kor)
                info_data["내용"].append(val)
        
        st.table(pd.DataFrame(info_data))

    st.divider()
    
    # 가격 분석 섹션
    st.subheader("📊 시세 대비 분석")
    anal_col1, anal_col2 = st.columns(2)
    
    # 동일 업종 평균 비교
    avg_biz_rent = df_raw[df_raw['businessMiddleCodeName'] == article['businessMiddleCodeName']]['monthlyRent'].mean()
    rent_diff_pct = ((article['monthlyRent'] - avg_biz_rent) / avg_biz_rent) * 100 if avg_biz_rent > 0 else 0
    
    with anal_col1:
        st.metric(f"동일 업종({article['businessMiddleCodeName']}) 대비 월세", 
                  f"{article['monthlyRent']:,}만원", 
                  delta=f"{rent_diff_pct:.1f}%", 
                  delta_color="inverse") # 월세는 낮을수록 좋으므로 inverse
        st.caption(f"동일 업종 평균 월세: {avg_biz_rent:,.0f}만원")

    # 동일 지역(역세권) 평균 비교
    station = article['nearSubwayStation']
    if station:
        avg_loc_premium = df_raw[df_raw['nearSubwayStation'] == station]['premium'].mean()
        premium_diff_pct = ((article['premium'] - avg_loc_premium) / avg_loc_premium) * 100 if avg_loc_premium > 0 else 0
        
        with anal_col2:
            st.metric(f"인근역({station}) 대비 권리금", 
                      f"{article['premium']:,}만원", 
                      delta=f"{premium_diff_pct:.1f}%", 
                      delta_color="inverse")
            st.caption(f"인근역 평균 권리금: {avg_loc_premium:,.0f}만원")
    else:
        with anal_col2:
            st.info("인근역 정보가 없어 지역 비교가 불가능합니다.")

    # 하단 바 (중개사 정보 등 간략히)
    st.divider()
    st.write(f"📝 **매물 설명**: {article['title']}")
    st.write(f"📅 **확인 일자**: {article['confirmedDateUtc']}")
