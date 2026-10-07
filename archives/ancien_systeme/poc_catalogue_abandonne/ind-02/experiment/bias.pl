head_pred(pattern_target,1).
body_pred(pattern_a,1).
body_pred(pattern_b,1).
body_pred(pattern_noise,1).

type(pattern_target,(entity,)).
type(pattern_a,(entity,)).
type(pattern_b,(entity,)).
type(pattern_noise,(entity,)).

direction(pattern_target,(in,)).
direction(pattern_a,(in,)).
direction(pattern_b,(in,)).
direction(pattern_noise,(in,)).

max_vars(1).
max_body(2).
