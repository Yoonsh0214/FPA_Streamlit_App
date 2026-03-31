# FPA WebApp (Football Performance Analysis)

FPA WebApp은 축구 경기의 실시간 로그를 기록하고, 이를 바탕으로 다양한 퍼포먼스 지표를 분석하는 웹 애플리케이션입니다. Python Flask를 기반으로 하며, 직관적인 웹 인터페이스를 통해 데이터를 입력하고 엑셀 파일로 분석 결과를 받아볼 수 있습니다.

## 주요 기능

### 1. 실시간 데이터 입력 (Live Logging)
- **축구장 인터페이스**: 웹 화면의 축구장 이미지를 클릭하여 선수의 위치 좌표(시작점, 끝점)를 쉽게 입력할 수 있습니다.
- **스탯 코드 입력**: 선수 번호, 액션 코드, 태그 등을 조합한 단축 코드로 빠르게 이벤트를 기록합니다. (예: `10ss8.k` -> 10번 선수가 8번 선수에게 키패스)
- **자동 태깅**: 입력된 액션과 좌표를 기반으로 성공/실패, 진전 패스(Progressive), 박스 안/밖(In-box/Out-box) 등의 태그가 자동으로 부여됩니다.

### 2. 데이터 분석 (Data Analysis)
- **패스 분석**: 패스의 거리(Short, Middle, Long)와 방향(Forward, Backward, Left, Right)을 자동으로 분류합니다.
- **공간 분석**: Final Third 진입, 페널티 박스(Penalty Area) 내 이벤트 등을 식별합니다.
- **고급 지표 산출**:
    - **xG (Expected Goals)**: 슈팅 위치에 따른 기대 득점 값을 계산합니다.
    - **종합 점수**: 선수별 패싱, 슈팅, 드리블, 수비, 결정력(Decision), 오프 더 볼(Off The Ball) 등의 종합 점수를 산출합니다.

### 3. 엑셀 내보내기 및 파일 분석
- **실시간 데이터 내보내기**: 기록된 로그를 바탕으로 즉시 분석을 수행하고, 결과가 포함된 엑셀 파일을 다운로드할 수 있습니다.
- **파일 업로드 분석**: 기존에 작성된 엑셀 파일('Data' 시트 포함)을 업로드하여 동일한 분석 로직을 거친 결과 파일을 받을 수 있습니다.
- **다양한 시트 제공**:
    - `Data`: 전체 원본 및 분석 데이터
    - `Tableau_Pass`: 태블로 시각화를 위한 형태 변환 데이터
    - `Pass_Summary`, `Shooting_Summary`, `Cross_Summary`: 부문별 요약 통계
    - `Final_Stats`: 선수별 종합 능력치 점수

## 설치 및 실행 (로컬)

1. **저장소 클론 (Clone Repository)**
   ```bash
   git clone https://github.com/Yoonsh0214/FPA_Streamlit_App.git
   cd FPA_WebApp
   ```

2. **의존성 패키지 설치**
   ```bash
   pip install -r requirements.txt
   ```

3. **애플리케이션 실행**
   ```bash
   python app.py
   ```
   서버가 시작되면 브라우저에서 `http://localhost:5001` 로 접속합니다.

## 배포 방법 (Render)

이 프로젝트는 `Render`를 통해 누구나 접속 가능한 웹사이트로 쉽게 배포할 수 있습니다.

1. **GitHub에 코드 푸시**
   - 이 프로젝트 코드를 본인의 GitHub 저장소에 업로드합니다.
   - `Procfile`과 `requirements.txt`가 포함되어 있어야 합니다.

2. **Render 회원가입 및 서비스 생성**
   - [Render.com](https://render.com)에 접속하여 회원가입(GitHub 계정 연동 추천)을 합니다.
   - Dashboard에서 **New +** 버튼을 누르고 **Web Service**를 선택합니다.

3. **저장소 연결**
   - 'Connect a repository' 목록에서 방금 올린 FPA WebApp 저장소를 선택합니다.

4. **설정 확인 및 배포**
   - **Name**: 원하는 서비스 이름 (예: `fpa-webapp`)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app` (자동으로 입력될 수 있습니다)
   - **Plan**: Free (무료) 선택
   - **Create Web Service** 버튼 클릭

5. **완료**
   - 배포가 완료되면 `https://fpa-webapp.onrender.com` 과 같은 주소로 접속할 수 있습니다.

## 프로젝트 구조

- `app.py`: Flask 메인 애플리케이션 파일. 라우팅 및 요청 처리를 담당합니다.
- `analysis.py`: 데이터 분석 핵심 로직이 담긴 모듈입니다.
- `templates/index.html`: 사용자 인터페이스(UI)를 구성하는 HTML 파일입니다.
- `static/`: 로고, 축구장 이미지 등 정적 파일을 저장하는 디렉토리입니다.
- `Procfile`: Render 배포를 위한 실행 명령어 설정 파일입니다.
