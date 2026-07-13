# data_design.md

- `user`：`user_id`、`username`、`password`、`role`、`display_name`
- `resource`：`resource_id`、`owner_id`、`scope`、`title`、`resource_type`、`file_name`、`tags`、`content_text`、`media_kinds`、`chunks`
- `chunk`：`chunk_id`、`resource_id`、`content`、`summary`、`location`、`location_text`、`modality`
- `citation`：`resource_id`、`title`、`scope`、`media_kinds`、`location`、`location_text`、`snippet`
- `qa_log`：`asked_at`、`user_id`、`question`、`provider`、`model`、`citations`
