const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const baseDir = process.cwd();
const sourcePath = path.join(baseDir, 'teacher_chinese_raw.txt');
const outputDir = path.join(baseDir, 'processed_data', 'avatar_knowledge');
const outputPath = path.join(outputDir, 'chinese_teacher.json');

const articleConfigs = [
  { title: '社会历史的决定性基础', startPage: 7, endPage: 11, author: '恩格斯', type: '论述文' },
  { title: '改造我们的学习', startPage: 12, endPage: 16, author: '毛泽东', type: '论述文' },
  { title: '人的正确思想是从哪里来的？', startPage: 17, endPage: 17, author: '毛泽东', type: '论述文' },
  { title: '实践是检验真理的唯一标准', startPage: 18, endPage: 22, author: '《光明日报》特约评论员', type: '论述文' },
  { title: '修辞立其诚', startPage: 23, endPage: 25, author: '张岱年', type: '论述文' },
  { title: '怜悯是人的天性', startPage: 26, endPage: 30, author: '卢梭', type: '论述文' },
  { title: '人应当坚持正义', startPage: 31, endPage: 35, author: '柏拉图', type: '论述文' },
  { title: '记念刘和珍君', startPage: 38, endPage: 42, author: '鲁迅', type: '纪念性散文' },
  { title: '为了忘却的记念', startPage: 43, endPage: 50, author: '鲁迅', type: '纪念性散文' },
  { title: '包身工', startPage: 52, endPage: 60, author: '夏衍', type: '报告文学' },
  { title: '荷花淀', startPage: 61, endPage: 65, author: '孙犁', type: '小说' },
  { title: '小二黑结婚（节选）', startPage: 66, endPage: 70, author: '赵树理', type: '小说' },
  { title: '党费', startPage: 71, endPage: 79, author: '王愿坚', type: '小说' },
  { title: '屈原列传', startPage: 82, endPage: 86, author: '司马迁', type: '文言文' },
  { title: '苏武传', startPage: 87, endPage: 92, author: '班固', type: '文言文' },
  { title: '过秦论', startPage: 93, endPage: 95, author: '贾谊', type: '文言文' },
  { title: '五代史伶官传序', startPage: 96, endPage: 99, author: '欧阳修', type: '文言文' },
  { title: '玩偶之家（节选）', startPage: 102, endPage: 116, author: '易卜生', type: '戏剧' },
  { title: '迷娘（之一）', startPage: 117, endPage: 118, author: '歌德', type: '诗歌' },
  { title: '致大海', startPage: 122, endPage: 124, author: '普希金', type: '诗歌' },
  { title: '自己之歌（节选）', startPage: 123, endPage: 123, author: '惠特曼', type: '诗歌' },
  { title: '树和天空', startPage: 124, endPage: 124, author: '特朗斯特罗姆', type: '诗歌' },
  { title: '燕歌行并序', startPage: 128, endPage: 129, author: '高适', type: '古诗词' },
  { title: '李凭箜篌引', startPage: 129, endPage: 129, author: '李贺', type: '古诗词' },
  { title: '锦瑟', startPage: 130, endPage: 130, author: '李商隐', type: '古诗词' },
  { title: '书愤', startPage: 131, endPage: 131, author: '陆游', type: '古诗词' },
];

function sha1(text) {
  return crypto.createHash('sha1').update(text, 'utf8').digest('hex');
}

function normalizeLine(line) {
  return line
    .replace(/\u0007/g, '')
    .replace(/[ \t]+/g, ' ')
    .replace(/^\s+|\s+$/g, '');
}

function cleanInlineText(text) {
  return text
    .replace(/\d+语文选择性必修中册/g, '')
    .replace(/第[一二三四五六七八九十]+单元\s*\d*/g, '')
    .replace(/选自《[^。；!\n]{0,120}[。；]?/g, '')
    .replace(/（[^（）]{0,40}出版社[^（）]{0,40}）/g, '')
    .replace(/人民出版社[^。；!\n]{0,80}[。；]?/g, '')
    .replace(/人民文学出版社[^。；!\n]{0,80}[。；]?/g, '')
    .replace(/江苏人民出版社[^。；!\n]{0,80}[。；]?/g, '')
    .replace(/河北教育出版社[^。；!\n]{0,80}[。；]?/g, '')
    .replace(/查良铮译。?/g, '')
    .replace(/楚图南译。?/g, '')
    .replace(/潘家洵译。?/g, '')
    .replace(/杨武能译。?/g, '')
    .replace(/《玩偶之家》演出图/g, '')
    .replace(/普希金向大海告别[^。；!\n]{0,40}/g, '')
    .replace(/歌唱的迷娘和威廉·迈斯特/g, '')
    .replace(/[a-z@#]\d*/g, '')
    .replace(/[ ]+/g, ' ')
    .trim();
}

function shouldDropLine(line) {
  if (!line) return true;
  if (/^普通高中教科书/.test(line)) return true;
  if (/^语文 选择性必修中册/.test(line)) return true;
  if (/^目录/.test(line)) return true;
  if (/^第[一二三四五六七八九十]+单元/.test(line)) return true;
  if (/^单元研习任务/.test(line)) return true;
  if (/^学习提示/.test(line)) return true;
  if (/^注：篇名前标有/.test(line)) return true;
  if (/^\d+\s*$/.test(line)) return true;
  if (/^第[一二三四五六七八九十]+单元 \d+$/.test(line)) return true;
  if (/^a ?〔/.test(line)) return true;
  if (/^[a-z@#]\s*〔/.test(line)) return true;
  if (/^[a-z]\s*$/.test(line)) return true;
  if (/^[A-Za-z]\s*[〔(（]/.test(line)) return true;
  if (/^[0-9@#]+\s*〔/.test(line)) return true;
  if (/^[\d@#]+ /.test(line) && line.includes('〔')) return true;
  if (/^后 记/.test(line)) return true;
  if (/^绿色印刷产品/.test(line)) return true;
  if (/^定价：/.test(line)) return true;
  if (/^·北京·/.test(line)) return true;
  if (/^(选自|人民出版社|江苏人民出版社|人民文学出版社|河北教育出版社)/.test(line)) return true;
  if (/^(楚图南译|潘家洵译|查良铮译|杨武能译)/.test(line)) return true;
  if (/^(作者简介|学习提示)$/.test(line)) return true;
  if (/^《.+》演出图$/.test(line)) return true;
  if (/^.+向大海告别/.test(line)) return true;
  if (/^歌唱的迷娘和威廉/.test(line)) return true;
  if (/^第[一二三四五六七八九十]+单元 \d+$/.test(line)) return true;
  if (/^[第]?[一二三四五六七八九十]+单元 ?\d*$/.test(line)) return true;
  if (/^\d+\s*语文\s*选择性必修中册$/.test(line)) return true;
  if (/^[a-z@#]\s*〔.*$/.test(line)) return true;
  if (/^[a-z@#0-9]+\s*[\)）]?\s*$/.test(line)) return true;
  if (/^[A-Za-z]\s*$/.test(line)) return true;
  if (/^[\d一二三四五六七八九十]+$/.test(line)) return true;
  if (/^(教育部组织编写|总 主 编：|本册主编：|编写人员：|责任编辑：|美术编辑：)/.test(line)) return true;
  return false;
}

function cleanPage(pageText) {
  const rawLines = pageText.split(/\r?\n/).map(normalizeLine);
  const kept = [];
  for (const line of rawLines) {
    if (shouldDropLine(line)) continue;
    kept.push(line);
  }
  return kept;
}

function mergeLines(lines) {
  const paragraphs = [];
  let buffer = '';
  for (const line of lines) {
    if (!line) {
      if (buffer) {
        paragraphs.push(buffer);
        buffer = '';
      }
      continue;
    }
    if (!buffer) {
      buffer = line;
      continue;
    }
    const shouldSplit =
      /[。！？；：”）】]$/.test(buffer) ||
      /^(一|二|三|四|五|六|七|八|九|十)[、 ]/.test(line) ||
      /^[(（]?[一二三四五六七八九十0-9]+[)）.]/.test(line) ||
      /^第[一二三四五六七八九十0-9]+[章节幕部分]/.test(line);
    if (shouldSplit) {
      paragraphs.push(buffer);
      buffer = line;
    } else {
      buffer += line;
    }
  }
  if (buffer) paragraphs.push(buffer);
  return paragraphs;
}

function summarize(text, maxLength = 220) {
  const compact = text.replace(/\s+/g, '').trim();
  if (compact.length <= maxLength) return compact;
  return compact.slice(0, maxLength) + '……';
}

function isBadParagraph(text) {
  if (!text) return true;
  if (text.length < 18) return true;
  if (/^(普通高中教科书|语文选择性必修中册|学习提示|单元研习任务|后记)/.test(text)) return true;
  if (/^(选自|人民出版社|江苏人民出版社|人民文学出版社|河北教育出版社)/.test(text)) return true;
  if (/(年版|译。|出版社|作家。|思想家、文学家。)/.test(text) && text.length < 80) return true;
  if (/^[a-z@#0-9〔〕（）() ]+$/.test(text)) return true;
  if (/木刻|演出图|合作$/.test(text)) return true;
  if (/^\d+语文选择性必修中册/.test(text)) return true;
  return false;
}

function buildRecords(article, paragraphs) {
  const cleanParagraphs = paragraphs
    .map((item) => cleanInlineText(item.replace(/\s+/g, '').trim()))
    .filter((item) => item && item !== article.title && item !== article.author)
    .filter((item) => item !== '（节选）' && item !== '（之一）' && item !== '第三幕')
    .filter((item) => !isBadParagraph(item));
  const joined = cleanParagraphs.join('\n').trim();
  const summarySeed = cleanParagraphs.slice(0, Math.min(4, cleanParagraphs.length)).join('');
  const summary = summarize(summarySeed || joined, 220);
  const sectionTitle = `${article.title}（${article.author}）`;

  const baseRecords = [
    {
      question: `${article.title}的主要内容是什么？`,
      answer: `${sectionTitle}是一篇${article.type}。教材正文可概括为：${summary}`,
      tag: 'summary',
    },
    {
      question: `${article.title}的主旨是什么？`,
      answer: `结合教材内容，${sectionTitle}的核心可从正文理解为：${summary}`,
      tag: 'theme',
    },
    {
      question: `${article.title}有哪些写作特点？`,
      answer: `${sectionTitle}可结合教材文本从语言、结构、人物/意象塑造与表达方式上分析。正文关键内容为：${summary}`,
      tag: 'features',
    },
  ];

  const chunkRecords = [];
  cleanParagraphs.forEach((content, idx) => {
    if (!content || content.length < 25) return;
    if (content.length > 420) {
      const pieces = content.match(/.{1,220}/g) || [content];
      pieces.forEach((piece, pieceIdx) => {
        if (!piece || piece.length < 25) return;
        chunkRecords.push({
          question: `${article.title}第${idx + 1}段第${pieceIdx + 1}部分讲了什么？`,
          answer: piece,
          tag: `chunk_${idx + 1}_${pieceIdx + 1}`,
        });
      });
      return;
    }
    chunkRecords.push({
      question: `${article.title}第${idx + 1}段讲了什么？`,
      answer: content,
      tag: `chunk_${idx + 1}`,
    });
  });

  return [...baseRecords, ...chunkRecords].map((item) => {
    const source = `教师(语文).pdf#${article.title}`;
    return {
      id: sha1(`${item.question}|${item.answer}|${source}`),
      avatar_id: 'chinese_teacher',
      role: '语文老师教材知识',
      question: item.question,
      answer: item.answer,
      source,
      section_title: article.title,
      author: article.author,
      category: article.type,
      tag: item.tag,
    };
  });
}

function main() {
  const raw = fs.readFileSync(sourcePath, 'utf8');
  const pages = raw.split('\f');
  const records = [];

  for (const article of articleConfigs) {
    const pageTexts = [];
    for (let pageNo = article.startPage; pageNo <= article.endPage; pageNo++) {
      const page = pages[pageNo - 1] || '';
      pageTexts.push(page);
    }

    const lines = pageTexts.flatMap(cleanPage);
    let articleLines = lines;

    const titleIndex = lines.findIndex((line) => line.includes(article.title.replace('（节选）', '').replace('（之一）', '')));
    if (titleIndex >= 0) {
      articleLines = lines.slice(titleIndex + 1);
    }

    const paragraphs = mergeLines(articleLines)
      .map((item) => item.replace(/\s+/g, ' ').trim())
      .filter((item) => item && item.length >= 10);

    if (!paragraphs.length) continue;

    records.push(...buildRecords(article, paragraphs));
  }

  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(records, null, 2), 'utf8');
  console.log(`generated ${records.length} records -> ${outputPath}`);
}

main();
