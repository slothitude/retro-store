# DIY Steam Box / Game Streaming Server Hardware Research

Research date: 2026-05-19
Purpose: 5 small form factor PCs running Sunshine (game streaming server), streaming to retro handhelds via Moonlight on LAN

---

## 1. Sunshine Minimum Hardware Requirements

### Official Requirements (LizardByte)
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | Intel Core i3 / AMD Ryzen 3 | Intel Core i5+ / AMD Ryzen 5+ |
| GPU | Any GPU with hardware encoding (QuickSync / NVENC / AMD AMF) | NVIDIA GTX/RTX with NVENC |
| RAM | 4 GB | 8 GB+ |
| OS | Windows 10+, Debian 12+, macOS 13+ | Windows 11 or Debian 13+ |
| Network | 5 GHz WiFi or wired | Gigabit Ethernet |

**Critical factor**: Hardware video encoding support. Without it, CPU software encoding degrades quality and latency severely.

### Hardware Encoder Support by GPU
| Encoder | GPU Family | Max Encode |
|---------|-----------|------------|
| Intel Quick Sync (VAAPI on Linux) | Intel UHD (Gen 12 / Alder Lake-N) | H.264 1080p60, HEVC 1080p60 (up to ~39 Mbps HW cap) |
| AMD AMF / VCN | Radeon Vega, RDNA2, RDNA3 | H.264 1080p60, HEVC 1080p60 |
| NVIDIA NVENC | GTX 10xx+ / RTX | H.264, HEVC, AV1 (RTX 40xx) |
| RK3588 VPU | Rockchip RK3588/RK3588S | H.264 up to 8K30, HEVC 4K60 (kernel patches needed) |

### Can Integrated Graphics Handle It?

**Intel UHD (N100)**: YES for 1080p60 H.264 streaming. The N100's Gen 12 iGPU with 24 EUs supports QuickSync hardware encoding of H.264 and HEVC at 1080p60. Verified working for non-gaming streaming (remote desktop, light gaming). HEVC has a ~39 Mbps hardware encoding bitrate ceiling -- beyond that it falls back to software encoding.

**AMD Vega (5800H/6800H)**: YES, comfortably. AMD's VCN encoder handles 1080p60 H.264 and HEVC well. The Radeon 680M (RDNA2, 6800H) and Radeon 760M (RDNA3, 7640HS) are even better, supporting AV1 encode.

**720p60 at low bitrate**: Any of the above handles this trivially. An N100 at 720p60 with 5-10 Mbps H.264 would barely break a sweat.

---

## 2. Mini PC Options for DIY Steam Boxes

### Tier 1: Under $100 (Budget / Basic)

| Model | CPU | GPU | RAM/Storage | Price (USD) | Sunshine 1080p60? | Power Draw |
|-------|-----|-----|-------------|-------------|-------------------|-------------|
| Generic J4125 | Intel Celeron J4125 (4C/4T, 2.0-2.7GHz) | Intel UHD 600 (Gen 9.5) | 8GB DDR4 / 128GB SSD | $50-80 (AliExpress) | Marginal (Gen 9.5 QuickSync, HEVC limited) | ~6W idle, ~15W load |
| Generic N5095 | Intel Celeron N5095 (4C/4T, 2.0-2.9GHz) | Intel UHD 16 EUs (Gen 12) | 8GB DDR4 / 256GB NVMe | $70-100 (AliExpress) | YES (H.264 1080p60 fine, HEVC OK at lower bitrate) | ~8W idle, ~20W load |
| NiPoGi/Chuwi N5105 | Intel Celeron N5105 (4C/4T, 2.0-2.9GHz) | Intel UHD 24 EUs (Gen 12) | 8GB DDR4 / 256GB NVMe | $80-110 (AliExpress) | YES (slightly better than N5095) | ~8W idle, ~22W load |

**Best pick under $100**: N5095 with 8GB RAM. Gen 12 QuickSync is the minimum you want. The J4125's Gen 9.5 graphics lack full HEVC encode support.

### Tier 2: $100-200 (Sweet Spot)

| Model | CPU | GPU | RAM/Storage | Price (USD) | Sunshine 1080p60? | Power Draw |
|-------|-----|-----|-------------|-------------|-------------------|-------------|
| GMKtec NucBox G3 | Intel N100 (4C/4T, 0.8-3.4GHz) | Intel UHD 24 EUs (Gen 12) | 8GB DDR4 / 128GB NVMe | $120-170 (AliExpress) | YES (H.264 1080p60 confirmed, HEVC 1080p60 with bitrate cap) | ~8W idle, ~25W load |
| Beelink EQ12 | Intel N100 | Intel UHD 24 EUs | 16GB DDR4 / 500GB NVMe | $150-200 (AliExpress/Amazon) | YES | ~10W idle, ~27W load |
| Beelink S12 Pro | Intel N100/N95 | Intel UHD 24/32 EUs | 16GB DDR4 / 500GB NVMe | $160-220 (AliExpress) | YES | ~10W idle, ~30W load |
| GMKtec NucBox G2 | Intel N100 | Intel UHD 24 EUs | 8GB / 256GB | ~$120-150 (AliExpress) | YES | ~8W idle, ~25W load |
| Generic N95 | Intel N95 (4C/4T, up to 3.4GHz) | Intel UHD 16 EUs | 8-16GB DDR4 / 256-512GB | $100-150 (AliExpress) | YES | ~8W idle, ~25W load |

**Best pick $100-200**: GMKtec NucBox G3 (N100) at $120-170. Best value for Sunshine streaming. Beelink EQ12 if you want 16GB RAM out of the box.

### Tier 3: $200-300 (Performance)

| Model | CPU | GPU | RAM/Storage | Price (USD) | Sunshine 1080p60? | Power Draw |
|-------|-----|-----|-------------|-------------|-------------------|-------------|
| TexHoo 5800H | AMD Ryzen 7 5800H (8C/16T, 3.2-4.4GHz) | Radeon Vega 8 | 16GB DDR4 / 512GB NVMe | ~$200-250 (AliExpress) | YES (excellent, AMF encode) | ~10W idle, ~45W load |
| Beelink SER5 | AMD Ryzen 5 5560U (6C/12T) | Radeon Vega 7 | 16GB DDR4 / 500GB NVMe | ~$200-280 (Amazon) | YES | ~8W idle, ~35W load |
| Beelink SER5 Pro | AMD Ryzen 7 5800H | Radeon Vega 8 | 16GB DDR4 / 500GB NVMe | ~$250-300 (Amazon) | YES (very capable) | ~10W idle, ~45W load |
| Minisforum UM760 (refurb) | AMD Ryzen 5 7640HS (6C/12T, up to 5.0GHz) | Radeon 760M (RDNA3) | 16GB DDR5 / 512GB NVMe | ~$209 (refurb, Minisforum) | YES (excellent, AV1 encode) | ~12W idle, ~45W load |

**Best pick $200-300**: TexHoo 5800H at ~$200-250 is the budget king here. Minisforum UM760 refurb at $209 if you can find it -- RDNA3 iGPU with AV1 encode is excellent.

### Tier 4: $300-500 (High Performance)

| Model | CPU | GPU | RAM/Storage | Price (USD) | Sunshine 1080p60? | Power Draw |
|-------|-----|-----|-------------|-------------|-------------------|-------------|
| Minisforum UM760 (new) | AMD Ryzen 5 7640HS | Radeon 760M (RDNA3) | 16GB DDR5 / 512GB PCIe 4.0 | ~$350-450 (Amazon) | YES (excellent) | ~12W idle, ~45W load |
| ZXIPC ZNR Pro | AMD Ryzen 7 5800H | Radeon Vega 8 | 16GB DDR4 / 512GB NVMe | ~$380 (AliExpress) | YES | ~10W idle, ~45W load |
| Beelink SER6 | AMD Ryzen 7 6800H | Radeon 680M (RDNA2) | 16GB LPDDR5 / 512GB | ~$350-450 | YES (excellent) | ~10W idle, ~45W load |
| Minisforum G7 PT | AMD Ryzen 7 7840HS | Radeon 780M (RDNA3) | 32GB DDR5 / 1TB | ~$305-500 | YES (best-in-class iGPU) | ~15W idle, ~55W load |

**Best pick $300-500**: Beelink SER6 (6800H with RDNA2) for ~$350-400 gives excellent streaming performance. Minisforum G7 PT if you want the absolute best iGPU.

---

## 3. SBC (Single Board Computer) Options

### Raspberry Pi 5
| Spec | Details |
|------|---------|
| CPU | BCM2712, 4x Cortex-A76 @ 2.4GHz |
| GPU | VideoCore VII |
| RAM | 4GB or 8GB LPDDR4X |
| Price | ~$60-80 (4GB), ~$80-100 (8GB) |
| Hardware Encoding | NO (VideoCore VII does NOT have H.264/HEVC hardware encoder) |
| Sunshine as HOST | NOT VIABLE for game streaming host. No hardware encoder. Software encoding would be too slow for 1080p60. |
| Sunshine as CLIENT | Excellent as Moonlight client (hardware decoding works well) |
| Power Draw | ~4W idle, ~9W load |

**Verdict**: Pi 5 is a great Moonlight CLIENT but cannot serve as a Sunshine HOST for game streaming due to lack of hardware video encoding.

### Orange Pi 5 (RK3588S)
| Spec | Details |
|------|---------|
| CPU | RK3588S, 4x Cortex-A76 @ 2.4GHz + 4x Cortex-A55 @ 1.8GHz |
| GPU | Mali-G610 MP4 |
| RAM | 4GB / 8GB / 16GB LPDDR4x |
| Price | ~$60 (4GB) / ~$80 (8GB) / ~$110 (16GB) (AliExpress) |
| Hardware Encoding | YES - H.264 up to 8K30, HEVC up to 4K60 (dual-core encoder) |
| Sunshine as HOST | POSSIBLE but requires effort. Needs kernel patches for V4L2 M2M encoding, FFmpeg VAAPI/DRM support. Mainline Linux support in progress (Collabora). |
| Power Draw | ~3W idle, ~8-12W load |
| Known Issues | HEVC encoding on mainline needs kernel patches (Armbian edge kernel 6.19+). H.264 encoding more mature. Community has achieved 4K60 HEVC encoding. |

**Verdict**: The RK3588 is the most promising SBC for Sunshine hosting. Hardware encoder is capable. The catch is software support -- you need Armbian with custom kernel patches, or ubuntu-rockchip with V4L2 M2M support configured. Not plug-and-play, but doable for a tinkerer. H.264 1080p60 should work well once configured.

### Orange Pi 5 Plus (RK3588)
Same SoC as Orange Pi 5 but with extra features: dual NIC, M.2 NVMe, more USB.
Price: ~$90-150 depending on RAM config.

### Radxa Rock 5B (RK3588)
Another RK3588 board. Similar capabilities to Orange Pi 5 Plus.
Price: ~$100-170 depending on config.

---

## 4. 3D Printed Case Designs

### Existing Geometric / Polyhedron PC Case Designs

**Icosahedron PC Case (Reddit / r/pcmasterrace)**
- 3D printed vertex joints connected by 2020 aluminium extrusion edges
- A proven hybrid approach for geometric cases
- Source: [Reddit build](https://www.reddit.com/r/pcmasterrace/comments/ixpm6a/first_custom_pc_build_wanted_to_do_something/)

**Princeton EPICS Icosahedron Computer Case**
- Academic project designing an icosahedron-shaped computer case
- More art installation than practical SFF
- Source: [Princeton EPICS](https://commons.princeton.edu/epics/about-2/spring-2021/icosahedroncomputercase/)

**SFF Steam Machine Case (3DCatt - Printables)**
- Valve Steam Machine replica case (167x168x225mm)
- Mini-ITX form factor
- Free STL download
- Source: [Printables - 3DCatt](https://www.printables.com/model/1493449-sff-mini-itx-steam-machine-case/related)

**"The Smash Box" Mini-ITX Case (Thingiverse)**
- Semi-portable, semi-modular Mini-ITX case
- Designed to be moved around the house
- Source: [Thingiverse](https://www.thingiverse.com/thing:2902468)

**Retro HP Mini PC Case (Printables)**
- Custom enclosure for repurposed mini PCs (e.g., HP ProDesk 600 G4 Mini)
- Designed for retro game emulation setups
- Source: [Printables](https://www.printables.com/model/1391409-retro-hp-mini-pc-case-retro-game-emulation-home-se)

**NeonSFF-1 (GitHub - Open Source)**
- Open-source 3D-printed SFF PC case (fits 180mm print volume)
- Source: [GitHub](https://github.com/berserkwarwolf/NeonSFF-1)

### Design Approach for Retro Store Steam Boxes

For mini PCs (which are typically 100-150mm square boxes), a custom geometric enclosure is very achievable:

**Construction Methods:**
1. **Full 3D print**: Print hollow polyhedron shells in 2-3 parts, insert mini PC inside
2. **Hybrid**: 3D-printed vertices + aluminium rod or PVC pipe edges (stronger, larger)
3. **Slip-over sleeve**: A decorative geometric shell that the mini PC slides into

**Platonic Solid Options (for 5 different boxes):**
1. **Tetrahedron** (4 faces) - smallest, sharpest angles
2. **Cube** (6 faces) - easiest to design, most practical
3. **Octahedron** (8 faces) - compact, interesting angles
4. **Dodecahedron** (12 faces) - classic, complex geometry
5. **Icosahedron** (20 faces) - most spherical, most complex

Each mini PC (~110x110x45mm) fits easily inside any of these shapes at reasonable scale. A dodecahedron with ~150mm face-to-face dimension would comfortably house an N100 mini PC with room for ventilation.

**Practical Considerations:**
- Ventilation is critical -- add mesh or perforated faces for airflow
- Use heat-set inserts for screw mounting the PC inside
- LED strip channels in the edges for retro-glow aesthetic
- Consider magnetic or snap-fit access panels for one face

---

## 5. Sunshine Setup on Linux/Windows

### Can Sunshine Run Headless?

YES. Multiple approaches:

| Method | Needs Dummy Plug? | Complexity | Notes |
|--------|-------------------|------------|-------|
| HDMI/DP Dummy Plug ($3-5) | Yes (physical) | Trivial | Simplest approach, ensures GPU initializes |
| Virtual Display via xrandr | No | Medium | Use `xrandr` + `cvt` to create virtual display |
| SSH Headless Setup (LizardByte guide) | No | Medium | Start X server + Sunshine over SSH |
| Windows headless | No (if RDP active) | Easy | Windows maintains virtual display via RDP |

**Simplest Setup for a Dedicated Streaming Box:**
1. Install Windows 11 or Debian Linux
2. Install Sunshine from [github.com/LizardByte/Sunshine](https://github.com/LizardByte/Sunshine)
3. Plug in an HDMI dummy plug ($3-5 on AliExpress) -- this is the easiest path
4. Configure Sunshine web UI at `https://<ip>:47990`
5. Set resolution to 1080p60 in Sunshine config
6. Install Steam, launch games
7. Connect Moonlight clients on handhelds

**For Linux (headless, no dummy plug):**
```bash
# Install Sunshine
sudo apt install sunshine

# Create virtual display
cvt 1920 1080 60
xrandr --newmode "1920x1080_60" <cvt_output>
xrandr --addmode Virtual-1 "1920x1080_60"
xrandr --output Virtual-1 --mode "1920x1080_60"

# Start Sunshine
sunshine
```

### Does Sunshine Need a Physical Display?

Not strictly, but the GPU needs SOME display output to capture frames from. Options:
- HDMI dummy plug (recommended, $3-5, ensures proper resolution detection)
- Virtual display (Linux only, more setup)
- RDP session (Windows, maintains virtual display when RDP is active)

### Recommended OS for Dedicated Streaming Box

**Windows 11**: Easiest setup, best game compatibility, Steam works perfectly. Downside: larger storage footprint, more overhead.

**Debian/Ubuntu Linux**: Lighter, lower power, free. Sunshine supports VAAPI encoding on Intel/AMD. Games limited to Linux-native + Proton. Best for simpler setups.

For a retro game streaming box that primarily runs indie/older games: Linux is fine.
For a box that needs to run anything Steam offers: Windows 11.

---

## 6. Power Consumption Summary

### Can These Run 24/7 as Always-On Game Servers?

YES. All options are very efficient for 24/7 operation.

| Device | Idle Power | Streaming Power | Annual Cost (24/7 idle @ $0.15/kWh) |
|--------|-----------|-----------------|--------------------------------------|
| Intel N100 mini PC | 8-10W | 25-34W | ~$13-15/year |
| Intel N5095 mini PC | ~8W | ~20W | ~$11/year |
| AMD 5800H mini PC | ~10W | ~45W | ~$14/year |
| AMD 6800H mini PC | ~10W | ~45W | ~$14/year |
| Orange Pi 5 (RK3588) | ~3W | ~8-12W | ~$4/year |
| Raspberry Pi 5 | ~4W | ~9W | ~$5/year |

For context, a single N100 mini PC running 24/7 costs about $1/month in electricity. Five of them would cost ~$5/month total at idle.

---

## 7. Recommended 5-Box Build Plan

### Option A: Budget Build (~$600-800 total for 5 boxes)

| Box # | Device | Price | Role |
|-------|--------|-------|------|
| 1 | GMKtec G3 (N100, 8GB/128GB) | ~$140 | Indie/retro game server |
| 2 | GMKtec G3 (N100, 8GB/128GB) | ~$140 | Indie/retro game server |
| 3 | Beelink EQ12 (N100, 16GB/500GB) | ~$170 | Mid-tier game server |
| 4 | Generic N5095 (8GB/256GB) | ~$85 | Light streaming / emulation |
| 5 | Orange Pi 5 (8GB, RK3588) | ~$80 | Tinkerer SBC server |

### Option B: Balanced Build (~$1,000-1,500 total for 5 boxes)

| Box # | Device | Price | Role |
|-------|--------|-------|------|
| 1 | Beelink EQ12 (N100, 16GB/500GB) | ~$170 | Always-on indie server |
| 2 | Beelink SER5 (5800H, 16GB/500GB) | ~$250 | Mid-tier gaming server |
| 3 | TexHoo 5800H (16GB/512GB) | ~$220 | Mid-tier gaming server |
| 4 | Beelink SER5 (5560U, 16GB/500GB) | ~$230 | Light gaming server |
| 5 | Minisforum UM760 refurb (7640HS, 16GB/512GB) | ~$210 | High-end game server |

### Option C: Performance Build (~$1,500-2,000 total for 5 boxes)

| Box # | Device | Price | Role |
|-------|--------|-------|------|
| 1 | Minisforum UM760 (7640HS, 16GB/512GB) | ~$350 | Primary game server (AV1 encode) |
| 2 | Beelink SER6 (6800H, 16GB/512GB) | ~$380 | High-end game server (RDNA2) |
| 3 | TexHoo 5800H (16GB/512GB) | ~$220 | Mid-tier game server |
| 4 | Beelink EQ12 (N100, 16GB/500GB) | ~$170 | Always-on indie/retro server |
| 5 | Minisforum G7 PT (7840HS, 32GB/1TB) | ~$400 | Flagship game server (RDNA3) |

### 3D Printed Cases Budget
- Filament: ~$20-30 per case (PLA/PETG)
- 5 cases: ~$100-150 total
- HDMI dummy plugs: ~$3-5 each, $15-25 total

---

## 8. Sources

### Sunshine Requirements & Setup
- [Sunshine Official Documentation](https://docs.lizardbyte.dev/projects/sunshine/v2025.122.141614/)
- [Sunshine GitHub Repository](https://github.com/LizardByte/Sunshine)
- [Sunshine Headless Setup - LizardByte](https://app.lizardbyte.dev/2023-09-14-remote-ssh-headless-sunshine-setup/)
- [Sunshine Without HDMI Dummy Plug - Kevin Tsui](https://kevintyk.com/2024/02/12/using-sunshine-without-hdmi-dummy-plug/)
- [Sunshine Configuration Guide 2025 - Reddit](https://www.reddit.com/r/MoonlightStreaming/comments/1iin0sx/updated_configuration_guide_with_chapters_for/)

### Intel N100 & Mini PCs
- [Intel N100 as Sunshine Host - Reddit](https://www.reddit.com/r/MoonlightStreaming/comments/1afddnd/intel_n100_as_host/)
- [N100 Mini PC for Streaming - XDA Developers](https://www.xda-developers.com/reasons-intel-n100-mini-pc-running-linux-perfect-streaming/)
- [N100 QuickSync 4K Transcoding - Reddit r/PleX](https://www.reddit.com/r/PleX/comments/19aonxu/intel_n100_quick_sync_4k_transcoding_which_linux/)
- [N100 vs Raspberry Pi - Jeff Geerling](https://www.jeffgeerling.com/blog/2025/intel-n100-better-value-raspberry-pi/)
- [QuickSync Benchmarks Database](https://quicksync.ktz.me/)
- [N100 Power Consumption - Reddit r/MiniPCs](https://www.reddit.com/r/MiniPCs/comments/17jwt52/how_much_wattage_a_n100_mini_pc_draws/)

### AMD Mini PCs
- [Minisforum UM760 - Amazon](https://www.amazon.com/MINISFORUM-UM760-Slim-Processor-Computer/dp/B0DFQ3YFXH)
- [Recommended Mini PC for Moonlight - Reddit](https://www.reddit.com/r/MoonlightStreaming/comments/1mmycu9/recommended_mini_pc_for_moonlight/)
- [AMD 5800H Power Consumption - Reddit](https://www.reddit.com/r/MiniPCs/comments/15f4ref/amd_5800h_as_mini_server_how_much_electricity_do/)
- [Intel N100 QuickSync HEVC Bitrate Limitation - Emby](https://emby.media/community/topic/146117-intel-quicksync-h265-max-bitrate-39mbits-falls-back-to-software-encoding-above-this-threshold/)

### SBC Options
- [Sunshine on Raspberry Pi 5 - Reddit](https://www.reddit.com/r/LizardByte/comments/1i522bs/using_sunshine_on_raspberry_pi_5/)
- [Orange Pi 5B 4K 120Hz Streaming - GitHub Gist](https://gist.github.com/safijari/043d6d016efac6cca030393f09f3f46f)
- [RK3588 HEVC Encoding Patches - Armbian Forum](https://forum.armbian.com/topic/57951-rk3588-kernel-patches-for-h265-hardware-encoding-and-hdmirx-edid-fix/)
- [RK3588 Mainline Linux Video Decoders - cnx-software](https://www.cnx-software.com/2026/02/27/rockchip-rk3588-rk3576-h-264-and-h-265-video-decoders-mainline-linux/)
- [FFmpeg HW Acceleration on RK3588 - GitHub](https://github.com/Joshua-Riek/ubuntu-rockchip/issues/246)

### 3D Printed Cases
- [SFF Steam Machine Case - Printables (3DCatt)](https://www.printables.com/model/1493449-sff-mini-itx-steam-machine-case/related)
- [Valve Steam Machine 3D Printed Build - YouTube](https://www.youtube.com/watch?v=csN5J56vQgg)
- [Icosahedron PC Build - Reddit](https://www.reddit.com/r/pcmasterrace/comments/ixpm6a/first_custom_pc_build_wanted_to_do_something/)
- [Princeton Icosahedron Computer Case](https://commons.princeton.edu/epics/about-2/spring-2021/icosahedroncomputercase/)
- [The Smash Box Mini-ITX Case - Thingiverse](https://www.thingiverse.com/thing:2902468)
- [Retro HP Mini PC Case - Printables](https://www.printables.com/model/1391409-retro-hp-mini-pc-case-retro-game-emulation-home-se)
- [NeonSFF-1 Open Source Case - GitHub](https://github.com/berserkwarwolf/NeonSFF-1)
- [Retro Mini PC Cases - Yeggi](https://www.yeggi.com/q/retro+mini+pc+case/)
