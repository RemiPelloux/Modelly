; Wolf Sheep Predation: wolves eat sheep, sheep eat grass, grass grows back.
;
; Written for Modelly from the published description of the NetLogo models library
; model "Wolf Sheep Predation" (Wilensky, 1997); not a copy of its code. Sheep and
; wolves wander at random and lose one unit of energy per tick. A sheep on green grass
; eats it and gains energy; the patch turns brown and grows back after a countdown. A
; wolf on a patch with sheep eats one. An animal with negative energy dies; each
; animal reproduces with a probability per tick, splitting its energy with its young.

breed [ sheep a-sheep ]
breed [ wolves wolf ]

turtles-own [ energy ]
patches-own [ countdown ]

to setup
  clear-all
  ask patches [
    set pcolor green
    if grass? [
      set countdown random grass-regrowth-time
      if random 2 = 0 [ set pcolor brown ]
    ]
  ]
  set-default-shape sheep "sheep"
  create-sheep initial-number-sheep [
    set color white
    set energy random (2 * sheep-gain-from-food)
    setxy random-xcor random-ycor
  ]
  set-default-shape wolves "wolf"
  create-wolves initial-number-wolves [
    set color black
    set energy random (2 * wolf-gain-from-food)
    setxy random-xcor random-ycor
  ]
  reset-ticks
end

to go
  if not any? turtles [ stop ]
  ask sheep [
    move
    if grass? [
      set energy energy - 1
      eat-grass
      death
    ]
    reproduce-sheep
  ]
  ask wolves [
    move
    set energy energy - 1
    eat-sheep
    death
    reproduce-wolves
  ]
  if grass? [ ask patches [ grow-grass ] ]
  tick
end

to move  ; turtle procedure: a random walk
  rt random 50
  lt random 50
  fd 1
end

to eat-grass  ; sheep procedure
  if pcolor = green [
    set pcolor brown
    set energy energy + sheep-gain-from-food
  ]
end

to reproduce-sheep  ; sheep procedure
  if random-float 100 < sheep-reproduce [
    set energy (energy / 2)
    hatch 1 [ rt random-float 360 fd 1 ]
  ]
end

to reproduce-wolves  ; wolf procedure
  if random-float 100 < wolf-reproduce [
    set energy (energy / 2)
    hatch 1 [ rt random-float 360 fd 1 ]
  ]
end

to eat-sheep  ; wolf procedure
  let prey one-of sheep-here
  if prey != nobody [
    ask prey [ die ]
    set energy energy + wolf-gain-from-food
  ]
end

to death  ; turtle procedure
  if energy < 0 [ die ]
end

to grow-grass  ; patch procedure
  if pcolor = brown [
    ifelse countdown <= 0
      [ set pcolor green
        set countdown grass-regrowth-time ]
      [ set countdown countdown - 1 ]
  ]
end
@#$#@#$#@
GRAPHICS-WINDOW
350
10
869
530
-1
-1
10.0
1
14
1
1
1
0
1
1
1
-25
25
-25
25
1
1
1
ticks
30.0

SLIDER
5
60
180
93
initial-number-sheep
initial-number-sheep
0
250
100
1
1
NIL
HORIZONTAL

SLIDER
5
95
180
128
sheep-gain-from-food
sheep-gain-from-food
0.0
50.0
4.0
1.0
1
NIL
HORIZONTAL

SLIDER
5
130
180
163
sheep-reproduce
sheep-reproduce
1.0
20.0
4.0
1.0
1
%
HORIZONTAL

SLIDER
185
60
350
93
initial-number-wolves
initial-number-wolves
0
250
50
1
1
NIL
HORIZONTAL

SLIDER
185
95
350
128
wolf-gain-from-food
wolf-gain-from-food
0.0
100.0
20.0
1.0
1
NIL
HORIZONTAL

SLIDER
185
130
350
163
wolf-reproduce
wolf-reproduce
0.0
20.0
5.0
1.0
1
%
HORIZONTAL

SLIDER
5
170
180
203
grass-regrowth-time
grass-regrowth-time
0
100
30
1
1
NIL
HORIZONTAL

SWITCH
185
170
350
203
grass?
grass?
0
1
-1000

@#$#@#$#@
Written for Modelly from the published description of the NetLogo Wolf Sheep Predation
model (Wilensky, U. 1997, Center for Connected Learning and Computer-Based Modeling,
Northwestern University). Not a copy of the original code.
@#$#@#$#@
