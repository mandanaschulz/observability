function extract_container_name(tag, timestamp, record)
    local path = record["source_file"] or ""
    local container_id = string.match(path, "/containers/([a-f0-9]+)/")
    if container_id then
        record["container_id"] = string.sub(container_id, 1, 12)
    end
    return 1, timestamp, record
end