scoreboard objectives add sorter_build dummy
$scoreboard players set #left sorter_build $(cells)
execute positioned ~3 ~-1 ~1 run function sorter:east/west_end
execute positioned ~3 ~-1 ~1 run function sorter:east/cells
tellraw @s {"text":"Склад построен. Кладите предметы во входной сундук; тип закрепляется, если положить его в любой сундук склада.","color":"green"}
