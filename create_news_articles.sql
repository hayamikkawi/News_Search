use ttds_search_enginel

CREATE TABLE IF NOT EXISTS news_articles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-increment primary key',

    -- URL 相关
    url VARCHAR(2048) NOT NULL COMMENT 'Original article URL',
    final_url VARCHAR(2048) NOT NULL COMMENT 'Final URL after redirection',
    feed_url VARCHAR(2048) NOT NULL COMMENT 'RSS feed source URL',

    -- RSS 元数据
    rss_title VARCHAR(1000) DEFAULT NULL COMMENT 'Title in RSS',
    rss_published_at DATETIME DEFAULT NULL COMMENT 'Published time in RSS',

    -- 抓取信息
    fetched_at DATETIME NOT NULL COMMENT 'Fetch time',
    http_status INT DEFAULT NULL COMMENT 'HTTP status code',
    error VARCHAR(500) DEFAULT NULL COMMENT 'Error message',

    -- 提取的文章内容
    text_ok BOOLEAN DEFAULT NULL COMMENT 'Whether text extraction was successful',
    title VARCHAR(1000) DEFAULT NULL COMMENT 'Extracted article title',
    author VARCHAR(500) DEFAULT NULL COMMENT 'Extracted author',
    date DATETIME DEFAULT NULL COMMENT 'Extracted article publication date',
    language VARCHAR(50) DEFAULT NULL COMMENT 'Article language',
    text MEDIUMTEXT DEFAULT NULL COMMENT 'Extracted main content',
    -- 索引和约束
    INDEX idx_url (url(255)),
    INDEX idx_feed_url (feed_url(255)),
    INDEX idx_fetched_at (fetched_at),
    INDEX idx_rss_published_at (rss_published_at),
    INDEX idx_text_ok (text_ok),
    INDEX idx_language (language),
    UNIQUE KEY uk_url_feed (url(255), feed_url(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='News articles table';