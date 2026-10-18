function sorter:west/cell
scoreboard players remove #left sorter_build 1
execute if score #left sorter_build matches ..0 positioned ~-6 ~0 ~0 run function sorter:west/east_end
execute if score #left sorter_build matches 1.. positioned ~-6 ~0 ~0 run function sorter:west/cells
