# inventory_risk_policy.md

# 재고 리스크 정책 문서

## 목적
현재 재고, 과거 출고이력, 입고예정, 출고예정을 반영하여 예상소진일과 위험등급을 정의한다.

## 예상소진일
```text
first date where projected_inventory <= 0
```

## Forecast 방식
```text
x = day_index
y = shipped_qty
predicted_demand = a * day_index + b
```

## 예상재고
```text
projected_inventory(t) =
projected_inventory(t-1)
+ planned_inbound_qty(t)
- confirmed_outbound_qty(t)
- predicted_demand(t)
```

## 위험등급
| 위험등급 | 기준 |
|---|---|
| HIGH | 7일 이내 소진 예상 |
| MEDIUM | 14일 이내 소진 예상 |
| LOW | 14일 초과 또는 소진 없음 |
| WATCH | 소진은 아니지만 안전재고 이하 도달 예상 |

## 데이터 부족 Fallback
| 출고이력 보유일수 | 예측 방식 |
|---|---|
| 30일 이상 | Linear Regression |
| 14일 이상 30일 미만 | 14일 이동평균 |
| 7일 이상 14일 미만 | 7일 이동평균 |
| 7일 미만 | 예측 불가 (INSUFFICIENT_DATA, 데이터 부족 안내) |
