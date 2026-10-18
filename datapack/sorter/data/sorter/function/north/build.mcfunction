scoreboard objectives add sorter_build dummy
$scoreboard players set #left sorter_build $(cells)
execute positioned ~1 ~-1 ~-3 run function sorter:north/west_end
execute positioned ~1 ~-1 ~-3 run function sorter:north/cells
tellraw @s {"text":"Склад построен. Кладите предметы во входной сундук; тип закрепляется, если положить его в любой сундук склада.","color":"green"}
