# FPA Web App Statistics & Calculation Manual

이 문서는 FPA Web App에서 사용되는 통계 지표와 계산 공식을 설명합니다.

## 1. 경기장 및 구역 정의 (stats_utils.py)
기본 경기장 규격은 **105m x 68m**입니다.

*   **Final Third (파이널 서드)**: X 좌표가 **70m 이상**인 구역
*   **Penalty Area (페널티 박스)**:
    *   X 좌표: **88.5m 초과**
    *   Y 좌표: **13.84m 초과 ~ 54.16m 미만**
*   **Progressive Pass (전진 패스)**: 패스 시작 지점보다 도착 지점의 X 좌표가 **10m 이상** 전진한 경우

---

## 2. 패스 분석 기준 (analysis.py)
패스는 거리와 방향에 따라 다음과 같이 분류됩니다.

### 거리 (Distance)
*   **Short**: 20m 미만
*   **Middle**: 20m 이상 ~ 40m 미만
*   **Long**: 40m 이상

### 방향 (Direction)
각도는 도착 지점과 시작 지점의 좌표 차이를 이용해 계산합니다.
*   **Forward (전방)**: 315도 ~ 45도
*   **Left (좌측)**: 45도 ~ 135도
*   **Backward (후방)**: 135도 ~ 225도
*   **Right (우측)**: 225도 ~ 315도

### xG (기대 득점) 계산
슈팅 위치와 골대 중심(105, 34) 사이의 거리를 기반으로 계산됩니다.
*   `xG = 1 / (1 + exp(0.14 * distance - 2.5))`

---

## 3. 스코어 산출 공식 (scoring.py)
모든 점수는 Raw Score(원점수)를 계산한 후, **Sigmoid 함수**를 통해 0~100점 사이의 점수로 변환됩니다.
*   *변환 공식*: `Score = 100 / (1 + exp(-steepness * (Raw - mid_point)))`

### 1) Passing Score (패싱 점수)
패스 성공률과 전진성, 찬스 메이킹을 종합적으로 평가합니다.

**Raw Score 계산식:**
```
(Pass_Success_Rate * 0.8) +
(Progressive_Pass_Success_Count * 1.5) +
(Key_Pass * 2.5) +
(Assist * 5) +
(PA_Pass_Success * 3) -
(Pass_Fail_Count * 0.5)
```
*   *Sigmoid 파라미터*: mid_point = -5, steepness = 0.08

### 2) Shooting Score (슈팅 점수)
득점 효율성과 골 결정력을 평가합니다. (xG 대비 득점이 중요)

**Raw Score 계산식:**
```
((Goals - Total_xG) * 10) +
(Total_xG * 15) +
(Headed_Goals * 5) +
(Outbox_Goals * 3)
```
*   *Sigmoid 파라미터*: mid_point = -2.2, steepness = 0.18

### 3) Cross Score (크로스 점수)
크로스 정확도와 위험 지역(중앙)으로의 공급 능력을 평가합니다.

**Raw Score 계산식:**
```
Base = (Cross_Accuracy * 0.7) + (ln(1 + Successful_Crosses) * 3)
Bonus = Central_PA_Cross_Success * 2.5
Raw = Base + Bonus
```
*   *Sigmoid 파라미터*: mid_point = -4, steepness = 0.1

### 4) Dribbling Score (드리블 점수)
돌파 성공과 실패에 따른 리스크를 평가합니다.

**Raw Score 계산식:**
```
(Breakthrough_Success * 3) -
((Failed_Dribble + Miss_Count) * 1) +
(Be_Fouled * 0.8)
```
*   *Sigmoid 파라미터*: mid_point = -2, steepness = 0.2

### 5) Defending Score (수비 점수)
적극적인 수비 성공과 실패를 평가합니다.

**Raw Score 계산식:**
```
(Successful_Tackles * 2) - (Failed_Tackles * 1) +
(Intercept_Count * 1.5) +
(Block_Count * 1.2) +
(Clear_Count * 1) +
(Aerial_Duels_Won * 1.5) - (Failed_Aerials * 0.5) +
(Duel_Win_Count * 0.5)
```
*   *Sigmoid 파라미터*: mid_point = -2.7, steepness = 0.15

---

## 4. 고급 지표 (Advanced Scores)

### 1) FST Score (First Touch - 안정성)
공을 받았을 때 다음 동작(패스, 돌파)을 성공적으로 이어가는 비율입니다.
*   **식**: `(Pass_Success + Breakthrough_Success) / (위의 분자 + Pass_Fail + Miss)`
*   *Sigmoid 파라미터*: mid_point = 80, steepness = 0.15 (기본점수 60)

### 2) OFF Score (Off The Ball - 움직임)
공을 받지 않은 상황에서의 기여도(좋은 위치 선정, 침투)를 평가합니다.
*   **Raw Score**:
    ```
    (Received_Assist * 3) +
    (Received_Key_Pass * 1.5) +
    SOT_Count + Goal_Count -
    (Offside_Count * 2)
    ```
*   *Sigmoid 파라미터*: mid_point = -1.6, steepness = 0.25

### 3) DEC Score (Decision Making - 판단력)
**Final Third(공격 지역)**에서의 플레이 성공률만을 따로 계산하여 판단력을 평가합니다.
*   **식**: `(FT_Pass_Success + FT_Breakthrough_Success) / (위의 분자 + FT_Pass_Fail + FT_Miss + FT_Offside)`
*   *Sigmoid 파라미터*: mid_point = 80, steepness = 0.15 (기본점수 60)
