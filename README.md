# assignment_230411


<사전 과제: paper trading 구현하기 >

  101개의 Golden Cross, Dead Cross 전략으로 작동하는 모의 트레이딩 봇을 구현하세요.

 [전략]
  - MA(10), MA(20)부터 파라미터 값을 1씩 증가시킨 MA(110), MA(120)까지의 101개의 간단한 전략 사용
전략1: MA(10)과 MA(20) 페어
전략2: MA(11)과 MA(21) 페어
… 
전략101: MA(110)과 MA(120) 페어
  - *golden cross 시 매수, **dead cross 시 매도 전략 사용
    (*golden cross: 단기 MA가 장기 MA를 돌파하고 올라 갈 때)
    (**dead cross: 단기 MA가 장기 MA를 뚫고 내려갈 때) 

 [데이터]
  - 기준 가격 캔들은 1m 사용
  - BTC close price 사용
  - Binance websocket 이용하여 데이터 가져오기

 [CI/CD]
  - github action, jenkins, circle CI등 자유롭게 사용

 [모니터링]
  - Dash및 그라파나 등 자유롭게 사용
  - 각 전략 별 수익률 및 balance 현황

 [인프라]
  - 클라우드 혹은 로컬에 Docker로 배포

 [제출방법]
  - github에 README를 포함하여 push후, 해당 링크 전달

 [제출기한]
  - 2023년 4월 11일 (화) 오후 11시 59분까지
  
  
  
  
# 과제 설명
  assignment_230411.py 실행 후 http://127.0.0.1:8050/ 접속시 보이는 Dash visualization 화면
  ![image](https://user-images.githubusercontent.com/60970842/231112402-5e37bcad-4f17-4d1d-8568-5b33c2505e3d.png)
  
  1. Portfolio Value(USDT): position value, unrealized pnl까지 합하여 총 자산을 USDT로 나타낸 숫자
  2. Current Position PnL: 현재 position의 총 pnl
  3. Current Position Amount: 현재 position의 갯수
  4. Stratrgy Cumulative PnL: 각 전략별 수익률. 전략 start -> end -> filled 되면 PnL에 반영
  5. Portfolio Value History: 1초마다 그래프에 <1. Portfolio Value(USDT)> 의 값을 기록하여 나타낸 차트

전략 Start
- 예를 들어 golden cross로 BUY가 되었을 때, 주문 체결 후 dead cross가 나기 전까지의 상태

전략 End
- 위 예시에서 dead cross로 해당 포지션에 대한 청산 주문(SELL 주문)이 나간 상태
- 주문이 체결(filled)되면 전략의 status는 0이 되고 websocket으로 받은 realized pnl을 strategy_d[전락번호][pnl]에 저장 후 
  자동으로 dash의 <4. Stratrgy Cumulative PnL>에 업데이트되도록 함
  
send_order 때마다 count += 1 을 적용하여 10번 주문시 전략이 자동으로 꺼지도록 해놓았음
- 꺼지지 않게 하려면 각 웹소켓의 on_message 부분의 코드 3줄을 지움
```python
    if count > 10:
        ws.close()
        sys.exit()
```

```python
    if count > 10:
        ws2.close()
        sys.exit()
```

