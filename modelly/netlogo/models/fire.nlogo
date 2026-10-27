; Fire: a fire spreads through a forest from its left edge.
;
; Written for Modelly from the published description of the NetLogo models library
; model "Fire" (Wilensky, 1997); not a copy of its code. Each patch holds a tree with
; probability density / 100. The trees of the left column catch fire; a burning tree
; sets fire to the trees on its four sides, then burns out. The share of trees burned
; jumps from small to almost all near a density of 59%, the site-percolation threshold
; of the square lattice.

globals [
  initial-trees   ; trees at the start
  burned-trees    ; trees that caught fire
]

to setup
  clear-all
  ask patches [
    if random-float 100 < density [ set pcolor green ]
  ]
  set initial-trees count patches with [ pcolor = green ]
  ask patches with [ pxcor = min-pxcor and pcolor = green ] [ ignite ]
  reset-ticks
end

to go
  if not any? patches with [ pcolor = red ] [ stop ]
  ask patches with [ pcolor = red ] [
    ask neighbors4 with [ pcolor = green ] [ ignite ]
    set pcolor red - 3.5   ; burned out
  ]
  tick
end

to ignite
  set pcolor red
  set burned-trees burned-trees + 1
end

to-report percent-burned
  report burned-trees / initial-trees * 100
end
@#$#@#$#@
GRAPHICS-WINDOW
200
10
710
521
-1
-1
2.0
1
10
1
1
1
0
0
0
1
-125
125
-125
125
1
1
1
ticks
30.0

SLIDER
5
40
190
73
density
density
0.0
99.0
57.0
1.0
1
%
HORIZONTAL

BUTTON
5
5
75
38
setup
setup
NIL
1
T
OBSERVER
NIL
NIL
NIL
NIL
1

BUTTON
80
5
150
38
go
go
T
1
T
OBSERVER
NIL
NIL
NIL
NIL
0

MONITOR
5
80
135
125
percent burned
percent-burned
1
1
11

@#$#@#$#@
Written for Modelly from the published description of the NetLogo Fire model
(Wilensky, U. 1997, Center for Connected Learning and Computer-Based Modeling,
Northwestern University). Not a copy of the original code.
@#$#@#$#@
