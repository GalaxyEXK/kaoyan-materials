---
generated_by: extract_to_md.py
source: "数学/高数/题/Test 1.docx"
source_sha256: "555702be0d0d293dab4927535f297bab68660ac86547e5422875aabcbe5f9906"
extractor_profile: "mineru-vlm-assets-v2"
---

# Test 1.docx

## Test 1

题

题1:

## 1. 题目

$$
I _ {k} = \int_ {0} ^ {\frac {k \pi}{2}} e ^ {- x ^ {2}} \sin 2 x d x \quad (k = 1, 2, 3)
$$

选项是比较 $I_{1}, I_{2}, I_{3}$ 的大小。

步骤 1: 分析被积函数的符号

根据三角函数的符号性质，先判断 $\sin 2x$ 在不同区间的正负：

\- 当 $0 < x < \frac{\pi}{2}$ 时， $\sin 2x > 0$ ；

\- 当 $\frac{\pi}{2} < x < \pi$ 时， $\sin 2x < 0$ ;

\- 当 $\pi < x < \frac{3\pi}{2}$ 时， $\sin 2x > 0$

结合 $e^{-x^2} > 0$ 恒成立，可得：

$$
\int_ {0} ^ {\frac {\pi}{2}} e ^ {- x ^ {2}} \sin 2 x d x > 0, \quad \int_ {\frac {\pi}{2}} ^ {\pi} e ^ {- x ^ {2}} \sin 2 x d x <   0, \quad \int_ {\pi} ^ {\frac {3 \pi}{2}} e ^ {- x ^ {2}} \sin 2 x d x > 0.
$$

## 步骤 2: 比较 $I_{1}$ 与 $I_{2}$

设 $I_{1} = \int_{0}^{\frac{\pi}{2}}e^{-x^{2}}\sin 2xdx$ ， $I_{2} = \int_{0}^{\pi}e^{-x^{2}}\sin 2xdx$ ，则：

$$
I _ {2} = \int_ {0} ^ {\pi} e ^ {- x ^ {2}} \sin 2 x d x = I _ {1} + \int_ {\frac {\pi}{2}} ^ {\pi} e ^ {- x ^ {2}} \sin 2 x d x.
$$

由于 $\int_{\frac{\pi}{2}}^{\pi}e^{-x^2}\sin 2x dx < 0$ ，因此：

$$
I _ {2} <   I _ {1}.
$$

## 步骤 3: 比较 $I_{2}$ 与 $I_{3}$

设 $I_{3} = \int_{0}^{\frac{3\pi}{2}}e^{-x^{2}}\sin 2x dx$ ，则：

$$
I _ {3} = \int_ {0} ^ {\frac {3 \pi}{2}} e ^ {- x ^ {2}} \sin 2 x d x = I _ {2} + \int_ {\pi} ^ {\frac {3 \pi}{2}} e ^ {- x ^ {2}} \sin 2 x d x.
$$

由于 $\int_{\pi}^{\frac{3\pi}{2}}e^{-x^2}\sin 2xdx > 0$ ，因此：

$$
I _ {3} > I _ {2}.
$$

步骤4：比较 $I_{1}$ 与 $I_{3}$

将 $I_{3}$ 拆分为 $I_{1}$ 与剩余区间的积分：

$$
I _ {3} = \int_ {0} ^ {\frac {3 \pi}{2}} e ^ {- x ^ {2}} \sin 2 x d x = I _ {1} + \int_ {\frac {\pi}{2}} ^ {\frac {3 \pi}{2}} e ^ {- x ^ {2}} \sin 2 x d x.
$$

其中：

$$
\int_ {\frac {\pi}{2}} ^ {\frac {3 \pi}{2}} e ^ {- x ^ {2}} \sin 2 x d x = \int_ {\frac {\pi}{2}} ^ {\pi} e ^ {- x ^ {2}} \sin 2 x d x + \int_ {\pi} ^ {\frac {3 \pi}{2}} e ^ {- x ^ {2}} \sin 2 x d x.
$$

对第二项积分做变量代换：令 $t = x - \frac{\pi}{2}$ ，则 $x = t + \frac{\pi}{2}$ ， $dx = dt$ ，当 $x = \pi$ 时 $t = \frac{\pi}{2}$ ，当 $x = \frac{3\pi}{2}$ 时

$t = \pi$ ，且：

$$
\sin 2 x = \sin (2 t + \pi) = - \sin 2 t,
$$

因此：

$$
\int_ {\pi} ^ {\frac {3 \pi}{2}} e ^ {- x ^ {2}} \sin 2 x d x = - \int_ {\frac {\pi}{2}} ^ {\pi} e ^ {- (t + \frac {\pi}{2}) ^ {2}} \sin 2 t d t.
$$

将其代回原积分（将 $t$ 换回 $x$ ）：

$$
\int_ {\frac {\pi}{2}} ^ {\frac {3 \pi}{2}} e ^ {- x ^ {2}} \sin 2 x d x = \int_ {\frac {\pi}{2}} ^ {\pi} \sin 2 x \left(e ^ {- x ^ {2}} - e ^ {- \left(x + \frac {\pi}{2}\right) ^ {2}}\right) d x.
$$

由于 $x \in \left(\frac{\pi}{2}, \pi\right)$ 时， $\sin 2x < 0$ ，且 $x < x + \frac{\pi}{2}$ 时， $x^2 < \left(x + \frac{\pi}{2}\right)^2$ ，故 $e^{-x^2} > e^{-(x + \frac{\pi}{2})^2}$ ，即

$e^{-x^2} - e^{-(x + \frac{\pi}{2})^2} > 0$ ，因此被积函数整体为负：

$$
\int_ {\frac {\pi}{2}} ^ {\pi} \sin 2 x \left(e ^ {- x ^ {2}} - e ^ {- \left(x + \frac {\pi}{2}\right) ^ {2}}\right) d x <   0.
$$

于是：

$$
I _ {3} = I _ {1} + (\text {负数}) \implies I _ {3} <   I _ {1}.
$$

最终结论

综合以上比较：

$$
I _ {2} <   I _ {3} <   I _ {1}
$$

故选(C)。

## 题2:

设函数

$$
f (x) = \lim _ {n \rightarrow \infty} \sqrt [ n ]{2 + (2 x) ^ {n} + x ^ {2 n}}, x \in (0, + \infty)
$$

则 $f(x)$ 在区间 $(0, +\infty)$ 内不可导的点的个数为（）

## 知识点 1:

对于 $\lim_{n\to\infty}\sqrt[n]{a_{1}^{n}+a_{2}^{n}+\cdots+a_{k}^{n}}$ （其中 $a_{i}>0$ ），有一个重要结论：

$$
\lim _ {n \rightarrow \infty} \sqrt [ n ]{a _ {1} ^ {n} + a _ {2} ^ {n} + \dots + a _ {k} ^ {n}} = \max \left\{a _ {1}, a _ {2}, \dots , a _ {k} \right\}
$$

你给出的极限

$$
\lim _ {n \rightarrow \infty} \sqrt [ n ]{a _ {1} ^ {n} + a _ {2} ^ {n} + \dots + a _ {k} ^ {n}}
$$

等于 $\max \{a_1, a_2, \ldots, a_k\}$ ，这个结论是正确的，我们直观解释一下为什么。

## 1. 理解核心思想

设 $M = \max\{a_{1}, \ldots, a_{k}\}$ 。

因为每个 $a_{i} > 0$ ，假设有某些 $a_{i}$ 等于 $M$ ，其余的小于 $M$ 。

对任意 $n$

$$
a _ {1} ^ {n} + a _ {2} ^ {n} + \dots + a _ {k} ^ {n}
$$

中，最大的项是 $M^n$ （可能不止一项），其他项都严格小于 $M^n$ 。

## 2.夹逼推导

设 $m$ 是值等于 $M$ 的 $a_{i}$ 的个数 $(m \geq 1)$ 。

显然：

$$
m M ^ {n} \leq a _ {1} ^ {n} + \dots + a _ {k} ^ {n} \leq k M ^ {n}
$$

取 $n$ 次方根：

$$
\sqrt [ n ]{m} \cdot M \leq \sqrt [ n ]{a _ {1} ^ {n} + \dots + a _ {k} ^ {n}} \leq \sqrt [ n ]{k} \cdot M
$$

因为 $\sqrt[n]{m} \to 1$ 且 $\sqrt[n]{k} \to 1$ ，所以由夹逼定理：

$$
\lim _ {n \rightarrow \infty} \sqrt [ n ]{a _ {1} ^ {n} + \dots + a _ {k} ^ {n}} = M
$$

## 3. 为什么“最大项主导极限”

把 $a_{i}^{n}$ 都写成 $M^n\cdot \left(\frac{a_i}{M}\right)^n$

$$
\sqrt [ n ]{a _ {1} ^ {n} + \dots + a _ {k} ^ {n}} = M \cdot \sqrt [ n ]{\left(\frac {a _ {1}}{M}\right) ^ {n} + \dots + \left(\frac {a _ {k}}{M}\right) ^ {n}}
$$

对于 $a_{i} < M$ ， $\left(\frac{a_i}{M}\right)^n\to 0$

对于 $a_{i} = M$ ，该项为1。

于是根号里面 $\rightarrow m$ ( $m$ 是等于 $M$ 的项数), 其实更精细地说:

根号里面的 $\left(\frac{a_i}{M}\right)^n\to 0$ 或 $= 1$ ，所以

$$
\sqrt [ n ]{m} \rightarrow 1
$$

再乘以外面的 $M$ 即得 $M$ 。

## 知识点 2:

我们要求的是

$$
F (x) = \int_ {0} ^ {h (x)} f (g (t)) d t
$$

对 $x$ 的导数。这里假设 $f, g, h$ 可导，且积分上限 $h(x)$ 可导。

## 1. 直接使用莱布尼茨法则

莱布尼茨积分法则（对含参变量的积分求导）的一般形式是：

$$
\frac {d}{d x} \int_ {a (x)} ^ {b (x)} \varphi (x, t) d t = \varphi (x, b (x)) \cdot b ^ {\prime} (x) - \varphi (x, a (x)) \cdot a ^ {\prime} (x) + \int_ {a (x)} ^ {b (x)} \frac {\partial}{\partial x} \varphi (x, t) d t
$$

如果被积函数中不显含 $x$ ，则最后一项为0。

在你的情况中：

\- $\varphi(x, t) = f(g(t))$ ，注意这里不显含 $x$ ，只依赖 $t$ 。

\- $a(x) = 0$ (常数), $b(x) = h(x)$ 。

于是：

$$
\frac {d F}{d x} = f (g (h (x))) \cdot h ^ {\prime} (x) - f (g (0)) \cdot 0
$$

因为 $a^{\prime}(x) = 0$ ，且 $\frac{\partial}{\partial x} f(g(t)) = 0$

结果很简单：

$$
\left| f (g (h (x))) \cdot h ^ {\prime} (x) \right|
$$

解：

## 5. 合并区间

$$
f (x) = \left\{ \begin{array}{l l} 1, & 0 <   x \leq 0. 5, \\ 2 x, & 0. 5 <   x <   2, \\ x ^ {2}, & x \geq 2. \end{array} \right.
$$

检查 $x = 0.5$ ：左右极限1与 $2\times 0.5 = 1$ ，连续。

x = 2: 左右 4 与 4，连续。

## 6. 不可导的点

一阶导数:

\- 在 $0 < x < 0.5, f'(x) = 0$

\- 在 $0.5 < x < 2, f'(x) = 2$

\- 在 $x > 2, f'(x) = 2x$

在 $x = 0.5$ :

左导 0，右导 $2 \rightarrow$ 不可导。

在 $x = 2$

左导 2，右导 4 → 不可导。

其他点可导。

所以在 $(0, +\infty)$ 内不可导的点是 $\{0.5, 2\}$ ，共2个点。

## 题3:

题目原文

已知函数 $f(x)$ 连续且 $\lim_{x\to 0}\frac{f(x)}{x} = 1$ ， $g(x) = \int_0^1 f(xt)dt$ ，求 $g^{\prime}(x)$ 并证明 $g^{\prime}(x)$ 在 $x = 0$ 处连续。

## 步骤1：先处理 $g(x)$ 的表达式（换元法）

令 $u = xt$ ，则 $t = \frac{u}{x}$ ， $dt = \frac{1}{x} du$ 。

当 t=0 时，u=0；当 t=1 时，u=x。

因此：

$$
g (x) = \int_ {0} ^ {1} f (x t) d t = \int_ {0} ^ {x} f (u) \cdot \frac {1}{x} d u = \frac {1}{x} \int_ {0} ^ {x} f (u) d u \quad (x \neq 0)
$$

接下来单独处理 $x = 0$ 的情况：

由条件 $\lim_{x\to 0}\frac{f(x)}{x} = 1$ ，可知 $\lim_{x\to 0}f(x) = 0$ ，又 $f(x)$ 连续，故 $f(0) = 0$ 。

当 $x = 0$ 时， $g(0) = \int_0^1 f(0)dt = \int_0^1 0dt = 0$ 。

所以：

$$
g (x) = \left\{ \begin{array}{l l} \frac {1}{x} \int_ {0} ^ {x} f (u) d u, & x \neq 0, \\ 0, & x = 0. \end{array} \right.
$$

步骤2：求 $g^{\prime}(x)$

(1) 当 $x \neq 0$ 时

用商的导数法则：

$$
g ^ {\prime} (x) = \frac {d}{d x} \left(\frac {1}{x} \int_ {0} ^ {x} f (u) d u\right) = \frac {f (x) \cdot x - \int_ {0} ^ {x} f (u) d u}{x ^ {2}}
$$

(2) 当 $x = 0$ 时

用导数定义：

$$
g ^ {\prime} (0) = \lim _ {x \rightarrow 0} \frac {g (x) - g (0)}{x - 0} = \lim _ {x \rightarrow 0} \frac {\frac {1}{x} \int_ {0} ^ {x} f (u) d u - 0}{x} = \lim _ {x \rightarrow 0} \frac {\int_ {0} ^ {x} f (u) d u}{x ^ {2}}
$$

由条件 $\lim_{x\to 0}\frac{f(x)}{x} = 1$ ，可知 $f(u)\sim u(u\to 0)$ ，或者用洛必达法则：

$$
\lim _ {x \to 0} \frac {\int_ {0} ^ {x} f (u) d u}{x ^ {2}} \stackrel {\text {洛必达}} {=} \lim _ {x \to 0} \frac {f (x)}{2 x} = \frac {1}{2} \lim _ {x \to 0} \frac {f (x)}{x} = \frac {1}{2} \times 1 = \frac {1}{2}
$$

综上， $g'(x)$ 的完整表达式：

$$
g ^ {\prime} (x) = \left\{ \begin{array}{l l} \frac {x f (x) - \int_ {0} ^ {x} f (u) d u}{x ^ {2}}, & x \neq 0, \\ \frac {1}{2}, & x = 0. \end{array} \right.
$$

步骤3：证明 $g^{\prime}(x)$ 在 $x = 0$ 处连续

即证明 $\lim_{x\to 0}g'(x) = g'(0) = \frac{1}{2}$ 。

计算 $\lim_{x\to 0}g'(x)$

$$
\lim _ {x \rightarrow 0} g ^ {\prime} (x) = \lim _ {x \rightarrow 0} \frac {x f (x) - \int_ {0} ^ {x} f (u) d u}{x ^ {2}}
$$

这是 $\frac{0}{0}$ 型，用洛必达法则：

$$
\lim _ {x \to 0}   {\frac {x f (x) - \int_ {0} ^ {x} f (u) d u}{x ^ {2}}}   {\overset {\text {洛必达}} {=}}   \lim _ {x \to 0}   {\frac {f (x) + x f ^ {\prime} (x) - f (x)}{2 x}} = \lim _ {x \to 0}   {\frac {x f ^ {\prime} (x)}{2 x}} = \lim _ {x \to 0}   {\frac {f ^ {\prime} (x)}{2}}
$$

也可以用泰勒展开：由 $\lim_{x\to 0}\frac{f(x)}{x} = 1$ ，得 $f(x) = x + o(x)$ 。

$$
x f (x) = x (x + o (x)) = x ^ {2} + o \left(x ^ {2}\right)
$$

$$
\int_ {0} ^ {x} f (u) d u = \int_ {0} ^ {x} (u + o (u)) d u = \frac {1}{2} x ^ {2} + o (x ^ {2})
$$

代入：

$$
\lim _ {x \rightarrow 0} \frac {x f (x) - \int_ {0} ^ {x} f (u) d u}{x ^ {2}} = \lim _ {x \rightarrow 0} \frac {x ^ {2} + o \left(x ^ {2}\right) - \frac {1}{2} x ^ {2} - o \left(x ^ {2}\right)}{x ^ {2}} = \lim _ {x \rightarrow 0} \frac {\frac {1}{2} x ^ {2} + o \left(x ^ {2}\right)}{x ^ {2}} = \frac {1}{2}
$$

而 $g^{\prime}(0) = \frac{1}{2}$ ，所以 $\lim_{x\to 0}g'(x) = g'(0)$ ，即 $g^{\prime}(x)$ 在 $x = 0$ 处连续。

最终答案

$$
g ^ {\prime} (x) = \left\{ \begin{array}{l l} \frac {x f (x) - \int_ {0} ^ {x} f (u) d u}{x ^ {2}}, & x \neq 0, \\ \frac {1}{2}, & x = 0. \end{array} \right.
$$

且 $g'(x)$ 在 x = 0 处连续。

(注：部分内容可能由 AI 生成)
