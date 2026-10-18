function sorter:south/cell
scoreboard players remove #left sorter_build 1
execute if score #left sorter_build matches ..0 positioned ~0 ~0 ~6 run function sorter:south/east_end
execute if score #left sorter_build matches 1.. positioned ~0 ~0 ~6 run function sorter:south/cells
