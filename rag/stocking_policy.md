# stocking_policy.md

# 적치 정책 문서

## 목적
입고예정 또는 입고완료 후 적치대기 상태의 상품에 대해 적치 위치를 추천하는 정책을 정의한다.

## 적치 기본 원칙
1. 보관조건이 일치해야 한다.
2. 적재 가능 CAPA가 있어야 한다.
3. 동일 SKU가 이미 존재하는 Location 또는 Zone을 우선 고려한다.
4. 동일 SKU가 없으면 Zone 잔여용량을 우선한다.
5. 잔여용량이 같으면 입구 또는 입고 Dock과 가까운 Zone을 우선한다.
6. 고회전 SKU는 가까운 Zone에 가중치를 부여한다.

## 적재 가능 Location 필터링
```text
Location.available_flag = 1
Product.storage_type = Zone.storage_type
Location.capacity - Location.occupied_qty >= inbound_qty
```

## 동일 SKU 우선 정책
동일 SKU가 이미 보관 중인 Location이 존재하면 해당 Location 또는 동일 Zone을 우선 추천한다. 동일 품목을 같은 Zone에 보관하면 재고 관리와 피킹 효율이 좋아진다.

## Zone 잔여용량 정책
동일 SKU가 없으면 잔여 CAPA가 큰 Zone을 우선한다.

## 거리 정책
잔여용량이 유사하면 입구 또는 Dock과 가까운 Zone을 우선한다.

## 고회전 SKU 정책
고회전 SKU는 출고 빈도가 높으므로 가까운 Zone에 가중치를 부여한다.

## 승인 정책
Agent는 적치 추천만으로 작업지시를 생성하지 않는다. 사용자 승인 후 적치지시를 생성한다.
