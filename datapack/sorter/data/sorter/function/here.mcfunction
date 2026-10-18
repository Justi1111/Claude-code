# /function sorter:here {cells:8}  -- direction = where you look
$execute if entity @s[y_rotation=-135..-45] run function sorter:east/build {cells:$(cells)}
$execute if entity @s[y_rotation=-45..45] run function sorter:south/build {cells:$(cells)}
$execute if entity @s[y_rotation=45..135] run function sorter:west/build {cells:$(cells)}
$execute unless entity @s[y_rotation=-135..135] run function sorter:north/build {cells:$(cells)}
