const statusText = document.getElementById("statusText");
const regionSelect = document.getElementById("region");
const spotSelect = document.getElementById("spot");
const cityInput = document.getElementById("city");
const themeInput = document.getElementById("theme");
const keywordsInput = document.getElementById("keywords");
const planResult = document.getElementById("planResult");
const contentResult = document.getElementById("contentResult");
const recommendResult = document.getElementById("recommendResult");
const memorialResult = document.getElementById("memorialResult");
const exportResult = document.getElementById("exportResult");
const downloadPackButton = document.getElementById("downloadPackButton");
const spotShowcase = document.getElementById("spotShowcase");
const heroImage = document.getElementById("heroImage");
const heroRegion = document.getElementById("heroRegion");
const heroSpotName = document.getElementById("heroSpotName");
const heroSpotSummary = document.getElementById("heroSpotSummary");
const locateButton = document.getElementById("locateButton");
const mapStatus = document.getElementById("mapStatus");
const travelSummary = document.getElementById("travelSummary");
const routeSteps = document.getElementById("routeSteps");

let spotOptions = { regions: [], spots: {} };
let lastAutoTheme = "";
let lastAutoKeywords = "";
let currentSpotName = "";
let mapInstance = null;
let drivingService = null;
let geolocationPlugin = null;
let routeMarkers = [];
let currentPosition = null;
let currentPositionLabel = "当前位置";
let geoWatchId = null;
let geoWatchTimer = null;

const highAccuracyPositionOptions = {
    enableHighAccuracy: true,
    timeout: 8000,
    maximumAge: 0,
};

const fallbackPositionOptions = {
    enableHighAccuracy: false,
    timeout: 12000,
    maximumAge: 300000,
};

const fieldLabels = {
    positioning: "方案定位",
    highlights: "核心亮点",
    activities: "活动流程",
    knowledge: "知识增强",
    plan_text: "策划长文",
    risk_tips: "风险提醒",
    title: "主标题",
    content_text: "传播长文",
    social_posts: "社交文案",
    video_script: "短视频脚本",
    host_lines: "主持人口播",
    route_name: "路线名称",
    route_steps: "路线步骤",
    fit_people: "适合人群",
    recommendation_text: "推荐长文",
    tips: "出行提示",
    memorial_text: "纪念长文",
    postcard_text: "明信片寄语",
    poster_title: "海报标题",
    album_cover: "相册封面",
    virtual_photo_prompt: "虚拟合影提示词",
    share_copy: "分享文案",
    souvenir_title: "纪念卡标题",
    topic: "主题",
    mermaid: "流程图代码",
    slides: "PPT 页面",
};

function collectPayload() {
    return {
        region: regionSelect.value,
        spot: spotSelect.value,
        theme: themeInput.value.trim(),
        city: cityInput.value.trim(),
        audience: document.getElementById("audience").value.trim(),
        duration: document.getElementById("duration").value.trim(),
        budget: document.getElementById("budget").value.trim(),
        keywords: keywordsInput.value.trim(),
    };
}

async function postJson(url, payload) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    return response.json();
}

function createValueNode(value) {
    if (Array.isArray(value)) {
        const list = document.createElement("ul");
        value.forEach((item) => {
            const listItem = document.createElement("li");
            if (item && typeof item === "object") {
                listItem.textContent = Object.entries(item)
                    .map(([key, text]) => `${key}：${text}`)
                    .join("；");
            } else {
                listItem.textContent = item;
            }
            list.appendChild(listItem);
        });
        return list;
    }
    if (value && typeof value === "object") {
        const wrapper = document.createElement("div");
        Object.entries(value).forEach(([key, text]) => {
            const paragraph = document.createElement("p");
            paragraph.textContent = `${key}：${text}`;
            wrapper.appendChild(paragraph);
        });
        return wrapper;
    }
    const paragraph = document.createElement("p");
    paragraph.textContent = value || "-";
    return paragraph;
}

function createSection(title, value) {
    const section = document.createElement("section");
    const heading = document.createElement("h3");
    heading.textContent = title;
    section.appendChild(heading);
    section.appendChild(createValueNode(value));
    return section;
}

function renderObjectResult(element, data) {
    element.innerHTML = "";
    element.classList.remove("empty-state");
    Object.entries(data).forEach(([key, value]) => {
        if (key === "brief" || key === "prompt_preview") {
            return;
        }
        const title = fieldLabels[key] || key.replace(/_/g, " ");
        element.appendChild(createSection(title, value));
    });
    if (!element.children.length) {
        element.classList.add("empty-state");
        element.textContent = "暂无结果";
    }
}

function clearTarget(action) {
    const targetMap = {
        plan: planResult,
        content: contentResult,
        recommend: recommendResult,
        memorial: memorialResult,
        ppt: exportResult,
        flowchart: exportResult,
    };
    const target = targetMap[action];
    if (target) {
        target.classList.add("empty-state");
        target.textContent = "正在生成...";
    }
}

function getCurrentSpot() {
    const currentRegion = regionSelect.value;
    const currentSpot = spotSelect.value;
    const candidates = spotOptions.spots[currentRegion] || [];
    return candidates.find((item) => item.name === currentSpot) || candidates[0];
}

function createEmptyRouteState(message) {
    travelSummary.classList.add("empty-state");
    travelSummary.innerHTML = `<p class="route-empty-text">${message}</p>`;
    routeSteps.classList.add("empty-state");
    routeSteps.innerHTML = `<p class="route-empty-text">${message}</p>`;
}

function clearRouteMarkers() {
    routeMarkers.forEach((marker) => marker.setMap(null));
    routeMarkers = [];
}

function createMarker(position, title, color) {
    return new AMap.Marker({
        position,
        title,
        label: { content: `<div style="padding:4px 8px;background:${color};color:#fff;border-radius:999px;font-size:12px;">${title}</div>`, direction: "top" },
    });
}

function getMapReady() {
    return typeof window.AMap !== "undefined" && window.APP_CONFIG && window.APP_CONFIG.amapWebKey;
}

function ensureMap() {
    if (!getMapReady()) {
        mapStatus.textContent = "高德地图脚本未加载成功。";
        return false;
    }
    if (!mapInstance) {
        mapInstance = new AMap.Map("mapContainer", {
            viewMode: "3D",
            zoom: 5,
            center: [116.397026, 39.918058],
            mapStyle: "amap://styles/darkblue",
        });
        drivingService = new AMap.Driving({
            map: mapInstance,
            hideMarkers: true,
            policy: AMap.DrivingPolicy.LEAST_TIME,
        });
        try {
            geolocationPlugin = new AMap.Geolocation({
                enableHighAccuracy: false,
                timeout: 8000,
                zoomToAccuracy: false,
            });
        } catch (e) {
            console.warn("AMap.Geolocation 初始化失败：", e);
            geolocationPlugin = null;
        }
    }
    return true;
}

function fillSpotCards(spots) {
    spotShowcase.innerHTML = "";
    spots.forEach((spot) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "spot-card";
        if (spot.name === spotSelect.value) {
            card.classList.add("active");
        }
        card.innerHTML = `
            <img src="${spot.cover}" alt="${spot.name}">
            <div>
                <strong>${spot.name}</strong>
                <span>${spot.city} · ${spot.best_time}</span>
                <p>${spot.summary}</p>
            </div>
        `;
        card.addEventListener("click", () => {
            spotSelect.value = spot.name;
            applySpotSelection();
        });
        spotShowcase.appendChild(card);
    });
}

function renderTravelSummary(route, spot) {
    const distance = route.distance ? `${(route.distance / 1000).toFixed(1)} 公里` : "待计算";
    const duration = route.time ? `${Math.round(route.time / 60)} 分钟` : "待计算";
    const taxiCost = route.taxi_cost ? `打车约 ${Math.round(route.taxi_cost)} 元` : "打车费用以实际为准";
    travelSummary.classList.remove("empty-state");
    travelSummary.innerHTML = `
        <article>
            <span class="travel-label">目的地</span>
            <strong class="travel-highlight">${spot.name}</strong>
            <span class="travel-meta">${spot.city} · ${spot.region}</span>
        </article>
        <article>
            <span class="travel-label">预计距离</span>
            <strong class="travel-highlight">${distance}</strong>
            <span class="travel-meta">驾车最优路线</span>
        </article>
        <article>
            <span class="travel-label">预计耗时</span>
            <strong class="travel-highlight">${duration}</strong>
            <span class="travel-meta">${taxiCost}</span>
        </article>
    `;
}

function renderRouteSteps(steps) {
    routeSteps.classList.remove("empty-state");
    routeSteps.innerHTML = "";
    const visibleSteps = steps.slice(0, 8);
    visibleSteps.forEach((step, index) => {
        const item = document.createElement("article");
        item.className = "route-step-item";
        const roadText = step.road && step.road !== "道路信息待更新" ? step.road : "道路待更新";
        const distanceText = step.distance ? `${step.distance} 米` : "距离待更新";
        item.innerHTML = `
            <strong>第 ${index + 1} 步</strong>
            <p>${step.instruction || "请按导航继续行驶"}</p>
            <span>${roadText} · ${distanceText}</span>
        `;
        routeSteps.appendChild(item);
    });
    if (steps.length > visibleSteps.length) {
        const note = document.createElement("p");
        note.className = "route-empty-text";
        note.textContent = `当前仅展示前 ${visibleSteps.length} 步，请结合地图继续查看完整路线。`;
        routeSteps.appendChild(note);
    }
}

function drawMarkers(origin, destination, spot) {
    clearRouteMarkers();
    const startMarker = createMarker(origin, currentPositionLabel, "#2563eb");
    const endMarker = createMarker(destination, spot.name, "#7c3aed");
    startMarker.setMap(mapInstance);
    endMarker.setMap(mapInstance);
    routeMarkers = [startMarker, endMarker];
}

function planRouteToCurrentSpot() {
    const spot = getCurrentSpot();
    if (!spot || !currentPosition) {
        createEmptyRouteState("请先定位当前位置后再规划路线。");
        return;
    }
    if (!ensureMap()) {
        return;
    }
    const destination = [spot.longitude, spot.latitude];
    mapStatus.textContent = `正在规划从当前位置到 ${spot.name} 的路线...`;
    drivingService.search(currentPosition, destination, (status, result) => {
        if (status !== "complete" || !result.routes || !result.routes.length) {
            mapStatus.textContent = "路线规划失败，请检查地图权限或稍后重试。";
            createEmptyRouteState("路线规划失败，请稍后重试。");
            return;
        }
        const route = result.routes[0];
        drawMarkers(currentPosition, destination, spot);
        renderTravelSummary(route, spot);
        renderRouteSteps(route.steps || []);
        mapStatus.textContent = `路线规划完成：${currentPositionLabel} → ${spot.name}`;
        mapInstance.setFitView();
    });
}

function applyCurrentPosition(coords, successText, positionLabel = "当前位置") {
    currentPosition = [coords.longitude, coords.latitude];
    currentPositionLabel = positionLabel;
    mapStatus.textContent = successText;
    planRouteToCurrentSpot();
}

function stopGeoWatch() {
    if (geoWatchId !== null && navigator.geolocation) {
        navigator.geolocation.clearWatch(geoWatchId);
    }
    geoWatchId = null;
    if (geoWatchTimer) {
        clearTimeout(geoWatchTimer);
    }
    geoWatchTimer = null;
}

function tryWatchedGeolocation() {
    if (!navigator.geolocation || typeof navigator.geolocation.watchPosition !== "function") {
        mapStatus.textContent = "定位失败";
        createEmptyRouteState("浏览器不支持持续定位监听，请稍后重试。");
        return;
    }
    stopGeoWatch();
    mapStatus.textContent = "常规定位仍未返回，正在监听系统位置更新...";
    createEmptyRouteState("已获得定位权限，正在等待系统位置服务返回最近一次可用坐标。无需重复授权，请稍候。");
    geoWatchId = navigator.geolocation.watchPosition(
        (pos) => {
            stopGeoWatch();
            applyCurrentPosition(pos.coords, "系统位置服务已返回坐标，正在规划路线。", "当前位置");
        },
        (err) => {
            stopGeoWatch();
            mapStatus.textContent = "定位失败";
            createEmptyRouteState(buildNativeGeolocationError(err, true));
        },
        fallbackPositionOptions,
    );
    geoWatchTimer = setTimeout(() => {
        stopGeoWatch();
        mapStatus.textContent = "定位失败";
        createEmptyRouteState("已获得定位权限，但系统位置服务长时间没有返回可用坐标。请确认 Windows“设置 → 隐私和安全性 → 位置”中的“位置服务”和“允许桌面应用访问你的位置”都已开启，然后重试。");
    }, 15000);
}

function buildNativeGeolocationError(err, hasRetried) {
    if (err.code === err.PERMISSION_DENIED) {
        return "浏览器定位权限被拒绝。请在浏览器地址栏左侧点击锁/信息图标，将“位置”权限改为“允许”，然后刷新页面重试。";
    }
    if (err.code === err.POSITION_UNAVAILABLE) {
        return "已获得定位权限，但系统定位服务没有返回可用坐标。请确认 Windows 系统定位已开启，并尽量关闭代理或 VPN 后重试。";
    }
    if (err.code === err.TIMEOUT) {
        if (hasRetried) {
            return "已获得定位权限，但系统定位服务在两次尝试中都未及时返回坐标。这通常不是权限没开，而是系统定位源响应慢；可确认 Windows 定位开启、网络正常后再试。";
        }
        return "定位请求超时，请稍后重试。";
    }
    return "定位失败，错误码：" + err.code + "，消息：" + (err.message || "未知");
}

function tryNativeGeolocation(hasRetried = false) {
    if (!navigator.geolocation) {
        mapStatus.textContent = "定位失败：浏览器不支持定位功能。";
        createEmptyRouteState("您的浏览器不支持定位功能，请使用 Chrome、Edge 或 Firefox 最新版本访问。");
        return;
    }
    mapStatus.textContent = hasRetried ? "高精度定位超时，正在切换为浏览器常规定位重试..." : "AMap 定位未成功，尝试浏览器原生定位...";
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            applyCurrentPosition(
                pos.coords,
                hasRetried ? "浏览器常规定位成功，正在规划路线。" : "浏览器定位成功，正在规划路线。",
            );
        },
        (err) => {
            if (!hasRetried && err.code === err.TIMEOUT) {
                createEmptyRouteState("已获得定位权限，但高精度定位响应较慢，正在自动切换为浏览器常规定位重试。请稍候，无需重复授权。");
                tryNativeGeolocation(true);
                return;
            }
            if (hasRetried && (err.code === err.TIMEOUT || err.code === err.POSITION_UNAVAILABLE)) {
                tryWatchedGeolocation();
                return;
            }
            mapStatus.textContent = "定位失败";
            createEmptyRouteState(buildNativeGeolocationError(err, hasRetried));
        },
        hasRetried ? fallbackPositionOptions : highAccuracyPositionOptions,
    );
}

function tryIpGeolocation() {
    // 服务端 IP 定位：完全不依赖浏览器 Geolocation API。
    // 通过 JSONP 直接调用高德 IP 定位 API（浏览器发起，绕开 WSL2 网络限制和 CORS）。
    mapStatus.textContent = "正在通过 IP 定位获取城市级位置...";
    createEmptyRouteState("正在通过 IP 定位获取您的城市级位置，无需浏览器定位权限...");
    var callbackName = "_amapIpCb" + Date.now();  // 生成唯一 JSONP 回调名。
    var script = document.createElement("script");  // 创建 JSONP script 标签。
    var amapKey = (window.APP_CONFIG && window.APP_CONFIG.amapWebKey) || "";  // 读取高德 Key。
    var timeoutId = setTimeout(function () {  // 设置 8 秒超时。
        cleanupJsonp();  // 超时后清理 JSONP。
        mapStatus.textContent = "IP 定位请求超时，尝试高德浏览器定位...";
        tryAmapGeolocation();  // 回退到高德浏览器定位。
    }, 8000);
    function cleanupJsonp() {  // 清理 JSONP 资源。
        clearTimeout(timeoutId);  // 清除超时定时器。
        if (window[callbackName]) { delete window[callbackName]; }  // 删除全局回调函数。
        if (script.parentNode) { script.parentNode.removeChild(script); }  // 移除 script 标签。
    }
    window[callbackName] = function (data) {  // 定义 JSONP 回调函数。
        cleanupJsonp();  // 先清理资源。
        if (data && data.status === "1" && data.rectangle) {  // 高德 API 返回成功且包含矩形坐标。
            var parts = data.rectangle.split(";");  // 格式："左下经度,左下纬度;右上经度,右上纬度"。
            if (parts.length === 2) {  // 确保有两组坐标。
                var lb = parts[0].split(",").map(Number);  // 解析左下角。
                var rt = parts[1].split(",").map(Number);  // 解析右上角。
                var lng = ((lb[0] + rt[0]) / 2).toFixed(6);  // 计算中心经度。
                var lat = ((lb[1] + rt[1]) / 2).toFixed(6);  // 计算中心纬度。
                var cityLabel = data.city || data.province || "未知城市";  // 读取城市名。
                currentPositionLabel = "IP定位（" + cityLabel + "）";  // 设置位置标签。
                applyCurrentPosition(  // 应用 IP 定位坐标并规划路线。
                    { longitude: parseFloat(lng), latitude: parseFloat(lat) },
                    "IP 定位成功（" + cityLabel + "），正在规划路线。",
                    currentPositionLabel,
                );
                return;  // IP 定位成功，直接返回。
            }
        }
        // IP 定位 API 返回失败，回退到高德浏览器定位。
        mapStatus.textContent = "IP 定位未成功，尝试高德浏览器定位...";
        tryAmapGeolocation();
    };
    script.src = "https://restapi.amap.com/v3/ip?key=" + encodeURIComponent(amapKey) + "&output=JSON&callback=" + callbackName;  // 组装 JSONP 请求 URL。
    script.onerror = function () {  // script 加载失败时。
        cleanupJsonp();  // 清理资源。
        mapStatus.textContent = "IP 定位请求失败，尝试高德浏览器定位...";
        tryAmapGeolocation();  // 回退到高德浏览器定位。
    };
    document.body.appendChild(script);  // 将 script 标签添加到页面以发起 JSONP 请求。
}

function tryAmapGeolocation() {
    // AMap Geolocation 插件定位：内部先尝试浏览器原生 API，
    // 失败后回退到 AMap 自己的 IP 定位（需要 securityCode 配置正确）。
    if (!ensureMap()) { return; }
    if (
        typeof AMap.Geolocation === "undefined" ||
        !geolocationPlugin ||
        typeof geolocationPlugin.getCurrentPosition !== "function"
    ) {
        mapStatus.textContent = "高德定位插件未加载，跳过。";
        tryNativeGeolocation();
        return;
    }
    mapStatus.textContent = "正在通过高德定位（需要浏览器授权，请在弹出的权限请求中点击「允许」）...";
    currentPositionLabel = "当前位置";
    geolocationPlugin.getCurrentPosition(function (status, result) {
        if (status === "complete" && result && result.position) {
            applyCurrentPosition(
                { longitude: result.position.lng, latitude: result.position.lat },
                "高德定位成功，正在规划路线。",
            );
            return;
        }
        var reason = "";
        if (result && result.message) { reason = result.message; }
        else if (status) { reason = "状态：" + status; }
        else { reason = "无更多错误详情"; }
        mapStatus.textContent = "高德定位未成功（" + reason + "），尝试浏览器原生定位...";
        createEmptyRouteState("高德定位未成功，系统将自动尝试浏览器原生定位；如弹出权限请求请点击「允许」。");
        tryNativeGeolocation();
    });
}

function requestCurrentLocation() {
    // 定位入口：优先使用服务端 IP 定位（绕开浏览器 API），
    // 再依次回退到高德插件、浏览器原生、watch 监听。
    stopGeoWatch();
    currentPosition = null;
    currentPositionLabel = "当前位置";
    tryIpGeolocation();
}

function applySpotSelection() {
    const spot = getCurrentSpot();
    if (!spot) {
        return;
    }
    const previousSpotName = currentSpotName;
    cityInput.value = spot.city;
    heroImage.src = `${spot.cover}?v=2`;
    heroRegion.textContent = spot.region;
    heroSpotName.textContent = spot.name;
    heroSpotSummary.textContent = spot.summary;
    const nextAutoTheme = `${spot.name}主题体验`;
    const nextAutoKeywords = (spot.tags || []).join("、");
    const currentTheme = themeInput.value.trim();
    const currentKeywords = keywordsInput.value.trim();
    if (!currentTheme || currentTheme === lastAutoTheme || (previousSpotName && currentTheme.includes(previousSpotName))) {
        themeInput.value = nextAutoTheme;
    }
    if (!currentKeywords || currentKeywords === lastAutoKeywords) {
        keywordsInput.value = nextAutoKeywords;
    }
    lastAutoTheme = nextAutoTheme;
    lastAutoKeywords = nextAutoKeywords;
    currentSpotName = spot.name;
    fillSpotCards(spotOptions.spots[regionSelect.value] || []);
    if (ensureMap()) {
        mapInstance.setCenter([spot.longitude, spot.latitude]);
        mapInstance.setZoom(10);
    }
    if (currentPosition) {
        planRouteToCurrentSpot();
    } else {
        createEmptyRouteState(`已选中 ${spot.name}，点击“定位并规划”后可查看真实路线。`);
        mapStatus.textContent = `已选中 ${spot.name}，等待定位。`;
    }
}

function renderRegionOptions() {
    regionSelect.innerHTML = "";
    spotOptions.regions.forEach((region) => {
        const option = document.createElement("option");
        option.value = region;
        option.textContent = region;
        regionSelect.appendChild(option);
    });
    const preferredRegion = spotOptions.regions.find((region) => {
        const spots = spotOptions.spots[region] || [];
        return spots.some((spot) => spot.city === cityInput.value.trim());
    });
    regionSelect.value = preferredRegion || spotOptions.regions[0] || "";
}

function renderSpotOptions() {
    const spots = spotOptions.spots[regionSelect.value] || [];
    spotSelect.innerHTML = "";
    spots.forEach((spot) => {
        const option = document.createElement("option");
        option.value = spot.name;
        option.textContent = `${spot.name} · ${spot.city}`;
        spotSelect.appendChild(option);
    });
    const preferredSpot = spots.find((spot) => spot.city === cityInput.value.trim());
    spotSelect.value = (preferredSpot && preferredSpot.name) || (spots[0] && spots[0].name) || "";
    applySpotSelection();
}

async function loadSpotOptions() {
    const response = await fetch("/api/spots/options");
    const result = await response.json();
    spotOptions = result.data;
    renderRegionOptions();
    renderSpotOptions();
}

async function downloadPack() {
    const payload = collectPayload();
    statusText.textContent = "正在下载：完整方案包";
    const response = await fetch("/api/export/markdown-pack", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename\*=UTF-8''([^;]+)/);
    link.href = url;
    link.download = match ? decodeURIComponent(match[1]) : "完整方案包.md";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    statusText.textContent = "下载完成：完整方案包";
}

async function handleAction(action) {
    const payload = collectPayload();
    clearTarget(action);
    statusText.textContent = `正在生成：${action}`;
    try {
        if (action === "plan") {
            const result = await postJson("/api/plan/generate", payload);
            renderObjectResult(planResult, result.data);
        }
        if (action === "content") {
            const result = await postJson("/api/content/generate", payload);
            renderObjectResult(contentResult, result.data);
        }
        if (action === "recommend") {
            const result = await postJson("/api/recommend/generate", payload);
            renderObjectResult(recommendResult, result.data);
        }
        if (action === "memorial") {
            const result = await postJson("/api/memorial/generate", payload);
            renderObjectResult(memorialResult, result.data);
        }
        if (action === "ppt") {
            const result = await postJson("/api/export/ppt-outline", payload);
            renderObjectResult(exportResult, result.data);
        }
        if (action === "flowchart") {
            const result = await postJson("/api/export/flowchart", payload);
            renderObjectResult(exportResult, result.data);
        }
        statusText.textContent = `生成完成：${action}`;
    } catch (error) {
        statusText.textContent = `生成失败：${error.message}`;
    }
}

regionSelect.addEventListener("change", renderSpotOptions);
spotSelect.addEventListener("change", applySpotSelection);
document.querySelectorAll("button[data-action]").forEach((button) => {
    button.addEventListener("click", () => handleAction(button.dataset.action));
});
downloadPackButton.addEventListener("click", downloadPack);
locateButton.addEventListener("click", requestCurrentLocation);
createEmptyRouteState("等待定位并规划路线...");
loadSpotOptions().catch((error) => {
    statusText.textContent = `景点加载失败：${error.message}`;
    mapStatus.textContent = `地图初始化失败：${error.message}`;
});
