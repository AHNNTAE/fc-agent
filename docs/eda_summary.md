### 주요 지표 기술통계 (전처리 후)

|                  |   mean |   std |   min |    50% |    max |
|:-----------------|-------:|------:|------:|-------:|-------:|
| possession       |  50    |  5.25 | 33    |  50    |  67    |
| shoot_total      |   6.28 |  2.68 |  0    |   6    |  17    |
| shoot_effective  |   4.88 |  2.31 |  0    |   5    |  14    |
| pass_try         | 107.54 | 21.95 | 54    | 106    | 219    |
| pass_rate        |   0.88 |  0.04 |  0.75 |   0.88 |   0.97 |
| through_pass_try |  16.64 |  6.79 |  1    |  16    |  45    |
| tackle_try       |  14.38 |  5.81 |  2    |  14    |  48    |
| goals_for        |   2.7  |  1.52 |  0    |   3    |   8    |
| goals_against    |   2.7  |  1.52 |  0    |   3    |   8    |

### 원본 결측치

|                      |   결측 건수 |
|:---------------------|--------:|
| division             |     864 |
| division_name        |     864 |
| controller           |      22 |
| goals_for            |      22 |
| goals_against        |      22 |
| possession           |      22 |
| average_rating       |      22 |
| foul                 |      22 |
| yellow_cards         |      22 |
| red_cards            |      22 |
| corner_kick          |      22 |
| offside              |      22 |
| dribble              |      22 |
| shoot_total          |      22 |
| shoot_effective      |      22 |
| shoot_in_penalty     |      22 |
| shoot_out_penalty    |      22 |
| shoot_heading        |      22 |
| pass_try             |      22 |
| pass_success         |      22 |
| short_pass_try       |      22 |
| short_pass_success   |      22 |
| long_pass_try        |      22 |
| long_pass_success    |      22 |
| through_pass_try     |      22 |
| through_pass_success |      22 |
| tackle_try           |      22 |
| tackle_success       |      22 |
| block_try            |      22 |
| block_success        |      22 |
| opp_shoot_total      |      22 |
| opp_shoot_effective  |      22 |

### 승리와 상관이 큰 지표 상위 5개

|                     |   |상관계수| |
|:--------------------|---------:|
| shoot_effective     |    0.42  |
| opp_shoot_effective |    0.42  |
| opp_shoot_total     |    0.357 |
| shoot_total         |    0.357 |
| possession          |    0.267 |

### 슈팅 거리별 골 성공률

| dist_bin    |   골 성공률(%) |   슈팅 수 |
|:------------|-----------:|-------:|
| (0.0, 0.05] |       86.5 |     74 |
| (0.05, 0.1] |       62.2 |   1880 |
| (0.1, 0.15] |       49.1 |   3578 |
| (0.15, 0.2] |       31.9 |   2664 |
| (0.2, 0.3]  |       21.6 |   1039 |
| (0.3, 1.5]  |        5.3 |    243 |
