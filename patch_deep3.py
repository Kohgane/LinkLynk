# -*- coding: utf-8 -*-
"""죽은 출처 교체 + CBD→일본. ★링크는 전부 직접 200 확인한 것만 쓴다."""
import io, sys
src = io.open("canibring_v1.py", encoding="utf-8").read()
if "cbd-to-japan" in src:
    print("이미 있다"); sys.exit(1)

DEAD = ('<a href="https://www.mhlw.go.jp/english/policy/health-medical/pharmaceuticals/01.html"'
        ' rel="noopener" target="_blank">Ministry of Health, Labour and Welfare &mdash;'
        ' bringing medicines for personal use into Japan</a>')
LIVE = ('<a href="https://jetprogramusa.org/wp-content/uploads/2025/03/'
        '2025-Yunyu-Kakuninsho-Import-of-Medication-Certification-Guide.pdf"'
        ' rel="noopener" target="_blank">Yunyu Kakunin-sho import-of-medication'
        ' guide, reproducing the MHLW quantity rules (PDF)</a>')
n = src.count(DEAD)
if n < 1:
    print("실패: 죽은 링크를 못 찾았다"); sys.exit(1)
src = src.replace(DEAD, LIVE)
print("  OK 죽은 출처 %d곳 교체" % n)

src += u'''

DEEP["cbd-to-japan"] = """
<h2>The rule changed, and most guides you will find are describing the old one</h2>
<p>Japan used to decide this by plant part: products made from cannabis stems and
seeds were acceptable, products from leaves and flowers were not. That test is
gone. Since 12 December 2024 the revised Cannabis Control Act judges the finished
product by how much THC is left in it, whatever part of the plant it came from.
If a page tells you to check that your CBD is &ldquo;stem and seed derived,&rdquo;
it was written for a law that no longer applies.</p>

<h2>The thresholds</h2>
<p>Residual THC limits are set by product form, and they are low:</p>
<p><b>Oils and fats that are liquid at room temperature, and powders</b> &mdash;
10 ppm (0.001%).</p>
<p><b>Water-soluble solutions</b> &mdash; 0.1 ppm (0.00001%).</p>
<p><b>Everything else</b> &mdash; 1 ppm (0.0001%).</p>
<p>A second phase of the same law took effect on 1 March 2025, adding licensing
and testing requirements on the supply side.</p>

<h2>Why a product that is legal at home can be 300 times over the limit</h2>
<p>In the United States and much of Europe, hemp is defined as cannabis
containing no more than 0.3% THC, and products are sold lawfully at that
ceiling. Convert the units: 0.3% is 3,000 ppm. Japan&rsquo;s limit for a CBD oil
is 10 ppm. A bottle that is entirely legal where you bought it, labelled as hemp
and marketed as non-intoxicating, can sit three hundred times above the Japanese
threshold and still be exactly what the label says. Nothing about the packaging
will tell you this. &ldquo;THC-free&rdquo; on a label is a marketing claim, not a
measurement against Japan&rsquo;s standard.</p>

<h2>Use is now an offence in itself</h2>
<p>The same revision created a cannabis use offence. Before it, the law reached
possession, transfer and cultivation; consumption as such was not separately
criminalised. It is now. This matters for travellers because it removes the
argument that you only used the product before arriving.</p>

<h2>What customs expects you to produce</h2>
<p>For a CBD product to clear, the documentation travellers are asked for is a
certificate of manufacture and a component analysis report from a laboratory
showing the THC content. That is a document you have to obtain from the maker
before you fly &mdash; it is not something you can assemble at the airport, and a
screenshot of a product page does not substitute for it.</p>

<h2>What we could not confirm</h2>
<p>We could not establish from an official Japanese source how the limits are
applied to a small quantity carried for personal use rather than to a commercial
import, or whether a traveller is in practice asked for the analysis report at
every border. We are not going to fill that gap with a guess. If the product
matters to you, ask a Regional Bureau Narcotics Control Department before you
book.</p>

<h2>Sources</h2>
<p><a href="https://www.mhlw.go.jp/stf/newpage_43079.html" rel="noopener" target="_blank">Ministry of Health, Labour and Welfare &mdash; phased enforcement of the revised Cannabis Control Act</a><br>
<a href="https://health-beauty-soleil.jp/news/%E3%80%90thc%E6%AE%8B%E7%95%99%E9%99%90%E5%BA%A6%E5%80%A4%E7%99%BA%E8%A1%A8%E3%80%91%E3%80%8C%E5%A4%A7%E9%BA%BB%E5%8F%96%E7%B7%A0%E6%B3%95%E5%8F%8A%E3%81%B3%E9%BA%BB%E8%96%AC%E5%8F%8A%E3%81%B3/" rel="noopener" target="_blank">Marunouchi Soleil Law Office &mdash; THC residual limit values, with the three thresholds and the 12 December 2024 date</a><br>
<a href="https://www.customs.go.jp/tokyo/english/yuubin/mayakuoyobikouseisinyaku.htm" rel="noopener" target="_blank">Tokyo Customs &mdash; narcotics, psychotropic drugs and raw materials for stimulants</a><br>
<a href="https://www.associatedkyotoprogram.org/bringing-medications-japan/" rel="noopener" target="_blank">Associated Kyoto Program &mdash; bringing medications into Japan</a></p>
<p style="opacity:.7">Last checked 2 October 2026. This area changed in December
2024 and again in March 2025. Treat anything older than that, here or elsewhere,
as describing a law that has been replaced.</p>
"""
'''

io.open("canibring_v1.py", "w", encoding="utf-8").write(src)
print("기록 완료 (%d바이트)" % len(src))
