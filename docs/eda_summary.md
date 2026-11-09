### 주요 지표 기술통계 (전처리 후)

|                  |   mean |   std |   min |    50% |    max |
|:-----------------|-------:|------:|------:|-------:|-------:|
| possession       |  50    |  5.24 | 33    |  50    |  67    |
| shoot_total      |   6.27 |  2.64 |  0    |   6    |  17    |
| shoot_effective  |   4.89 |  2.26 |  0    |   5    |  15    |
| pass_try         | 107.69 | 21.91 | 53    | 105    | 219    |
| pass_rate        |   0.88 |  0.04 |  0.72 |   0.88 |   0.98 |
| through_pass_try |  16.46 |  7.03 |  1    |  16    |  65    |
| tackle_try       |  14.88 |  6.1  |  1    |  14    |  48    |
| goals_for        |   2.7  |  1.51 |  0    |   3    |  10    |
| goals_against    |   2.7  |  1.51 |  0    |   3    |  10    |

### 원본 결측치

|                      |   결측 건수 |
|:---------------------|--------:|
| division             |    2540 |
| division_name        |    2540 |
| controller           |      78 |
| goals_for            |      78 |
| goals_against        |      78 |
| possession           |      78 |
| average_rating       |      78 |
| foul                 |      78 |
| yellow_cards         |      78 |
| red_cards            |      78 |
| corner_kick          |      78 |
| offside              |      78 |
| dribble              |      78 |
| shoot_total          |      78 |
| shoot_effective      |      78 |
| shoot_in_penalty     |      78 |
| shoot_out_penalty    |      78 |
| shoot_heading        |      78 |
| pass_try             |      78 |
| pass_success         |      78 |
| short_pass_try       |      78 |
| short_pass_success   |      78 |
| long_pass_try        |      78 |
| long_pass_success    |      78 |
| through_pass_try     |      78 |
| through_pass_success |      78 |
| tackle_try           |      78 |
| tackle_success       |      78 |
| block_try            |      78 |
| block_success        |      78 |
| opp_shoot_total      |      78 |
| opp_shoot_effective  |      78 |

### 승리와 상관이 큰 지표 상위 5개

|                     |   |상관계수| |
|:--------------------|---------:|
| shoot_effective     |    0.409 |
| opp_shoot_effective |    0.409 |
| opp_shoot_total     |    0.346 |
| shoot_total         |    0.346 |
| possession          |    0.272 |

### 슈팅 거리별 골 성공률

| dist_bin    |   골 성공률(%) |   슈팅 수 |
|:------------|-----------:|-------:|
| (0.0, 0.05] |       81.9 |    204 |
| (0.05, 0.1] |       62.9 |   5226 |
| (0.1, 0.15] |       50.2 |  10355 |
| (0.15, 0.2] |       32.5 |   8093 |
| (0.2, 0.3]  |       20.9 |   3266 |
| (0.3, 1.5]  |        4.5 |    695 |
