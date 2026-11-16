### 주요 지표 기술통계 (전처리 후)

|                  |   mean |   std |   min |    50% |    max |
|:-----------------|-------:|------:|------:|-------:|-------:|
| possession       |  50    |  5.25 | 22    |  50    |  78    |
| shoot_total      |   6.31 |  2.64 |  0    |   6    |  18    |
| shoot_effective  |   4.92 |  2.26 |  0    |   5    |  15    |
| pass_try         | 107.24 | 22.1  | 37    | 105    | 219    |
| pass_rate        |   0.88 |  0.04 |  0.71 |   0.88 |   0.98 |
| through_pass_try |  16.16 |  6.96 |  1    |  15    |  65    |
| tackle_try       |  15    |  6.05 |  1    |  14    |  48    |
| goals_for        |   2.72 |  1.51 |  0    |   3    |  10    |
| goals_against    |   2.72 |  1.51 |  0    |   3    |  10    |

### 원본 결측치

|                      |   결측 건수 |
|:---------------------|--------:|
| division             |    3377 |
| division_name        |    3377 |
| controller           |     111 |
| goals_for            |     111 |
| goals_against        |     111 |
| possession           |     111 |
| average_rating       |     111 |
| foul                 |     111 |
| yellow_cards         |     111 |
| red_cards            |     111 |
| corner_kick          |     111 |
| offside              |     111 |
| dribble              |     111 |
| shoot_total          |     111 |
| shoot_effective      |     111 |
| shoot_in_penalty     |     111 |
| shoot_out_penalty    |     111 |
| shoot_heading        |     111 |
| pass_try             |     111 |
| pass_success         |     111 |
| short_pass_try       |     111 |
| short_pass_success   |     111 |
| long_pass_try        |     111 |
| long_pass_success    |     111 |
| through_pass_try     |     111 |
| through_pass_success |     111 |
| tackle_try           |     111 |
| tackle_success       |     111 |
| block_try            |     111 |
| block_success        |     111 |
| opp_shoot_total      |     111 |
| opp_shoot_effective  |     111 |

### 승리와 상관이 큰 지표 상위 5개

|                     |   |상관계수| |
|:--------------------|---------:|
| shoot_effective     |    0.405 |
| opp_shoot_effective |    0.405 |
| opp_shoot_total     |    0.342 |
| shoot_total         |    0.342 |
| possession          |    0.272 |

### 슈팅 거리별 골 성공률

| dist_bin    |   골 성공률(%) |   슈팅 수 |
|:------------|-----------:|-------:|
| (0.0, 0.05] |       82.5 |    280 |
| (0.05, 0.1] |       63.1 |   6906 |
| (0.1, 0.15] |       50.4 |  13912 |
| (0.15, 0.2] |       32.8 |  10841 |
| (0.2, 0.3]  |       20.3 |   4465 |
| (0.3, 1.5]  |        4.7 |    978 |
