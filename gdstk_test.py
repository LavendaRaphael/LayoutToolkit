import gdstk
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union

def analyze_by_gdstk(gds_path, layer, datatype, target_x, target_y, search_range=10.0):
    """
    使用 gdstk + shapely 根据坐标抓取对应的 CD/Space 和 Tone (增强稳健性版)
    """
    # 1. 快速加载 GDSII / OASIS 文件
    library = gdstk.read_gds(gds_path) if gds_path.endswith('.gds') else gdstk.read_oas(gds_path)
    top_cells = library.top_level()
    if not top_cells:
        print("❌ 错误: 未找到 Top Cell")
        return
    top_cell = top_cells[0]
    
    # 2. 提取指定 Layer 和 Datatype 的多边形（include_paths=True 自动处理 Path）
    all_polygons = top_cell.get_polygons(include_paths=True)
    polygons = [p for p in all_polygons if p.layer == layer and p.datatype == datatype]
    
    if not polygons:
        print(f"❌ 错误: 未找到 Layer {layer}, Datatype {datatype} 的图形")
        return

    # 3. 判定 Tone：使用 gdstk 原生的 contain 函数
    target_point = (target_x, target_y)
    is_inside = False
    
    for poly in polygons:
        if poly.contain(target_point):
            is_inside = True
            break  
            
    tone = "Pattern (Dark)" if is_inside else "Space (Clear)"
    print(f"========= gdstk 坐标 ({target_x}, {target_y}) 分析 =========")
    print(f"Tone : {tone}")

    # 4. 测量 CD / Space (借助 Shapely 进行十字线段裁剪)
    pt_shapely = Point(target_x, target_y)
    search_bbox = pt_shapely.buffer(search_range).envelope
    
    nearby_shapely_polys = []
    for poly in polygons:
        min_p, max_p = poly.bounding_box()
        poly_bbox = Polygon([(min_p[0], min_p[1]), (max_p[0], min_p[1]), (max_p[0], max_p[1]), (min_p[0], max_p[1])])
        if search_bbox.intersects(poly_bbox):
            # 增加对多边形顶点的安全校验
            try:
                if hasattr(poly, "points") and len(poly.points) >= 3:
                    nearby_shapely_polys.append(Polygon(poly.points))
            except Exception as e:
                # 兼容处理带孔洞或特殊结构的 Polygon
                continue
            
    if not nearby_shapely_polys:
        print("⚠️ 提示: 搜索范围内未找到有效的几何边界，CD/Space 测算结果可能为 0")
        return

    # 合并附近的所有多边形
    local_merged_poly = unary_union(nearby_shapely_polys)

    # 拉出十字探测线 (Ruler)
    ruler_h = LineString([(target_x - search_range, target_y), (target_x + search_range, target_y)])
    ruler_v = LineString([(target_x, target_y - search_range), (target_x, target_y + search_range)])

    if is_inside:
        # 点在图形内 -> 测 CD (求交集)
        intersect_h = ruler_h.intersection(local_merged_poly)
        intersect_v = ruler_v.intersection(local_merged_poly)
        cd_x = get_covering_segment_length(intersect_h, target_x, 'x')
        cd_y = get_covering_segment_length(intersect_v, target_y, 'y')
        print(f"CD_X : {cd_x:.4f} um")
        print(f"CD_Y : {cd_y:.4f} um")
    else:
        # 点在图形外 -> 测 Space (求差集)
        space_h = ruler_h.difference(local_merged_poly)
        space_v = ruler_v.difference(local_merged_poly)
        sp_x = get_covering_segment_length(space_h, target_x, 'x')
        sp_y = get_covering_segment_length(space_v, target_y, 'y')
        print(f"Space_X : {sp_x:.4f} um")
        print(f"Space_Y : {sp_y:.4f} um")

def get_covering_segment_length(geometry, target_coord, axis='x'):
    """辅助函数：提取包含目标坐标的线段长度"""
    if geometry.is_empty: 
        return 0.0
    geoms = geometry.geoms if hasattr(geometry, 'geoms') else [geometry]
    for line in geoms:
        if isinstance(line, LineString):
            coords = list(line.coords)
            if len(coords) < 2:
                continue
            if axis == 'x':
                x_coords = [pt[0] for pt in coords]
                x_min, x_max = min(x_coords), max(x_coords)
                if x_min <= target_coord <= x_max: 
                    return x_max - x_min
            else:
                y_coords = [pt[1] for pt in coords]
                y_min, y_max = min(y_coords), max(y_coords)
                if y_min <= target_coord <= y_max: 
                    return y_max - y_min
    return 0.0

# 示例运行
# analyze_by_gdstk("test.oas", layer=1, datatype=0, target_x=0, target_y=0.3)

analyze_by_gdstk("test.oas", layer=1, datatype=0, target_x=0, target_y=0.3)
analyze_by_gdstk("test.oas", layer=1, datatype=0, target_x=-0.2, target_y=0.3)